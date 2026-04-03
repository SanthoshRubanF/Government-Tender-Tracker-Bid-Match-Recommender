from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Iterable

import pandas as pd

from tender_tracker.scraper import build_fingerprint, normalize_tender_title


UTC = timezone.utc
PREFERRED_JOURNAL_MODES = ("WAL", "TRUNCATE", "PERSIST", "MEMORY", "OFF")


@dataclass
class SyncSnapshot:
    total_tenders: int
    last_successful_sync_at: str | None
    latest_sync_status: str | None
    latest_sync_message: str | None
    latest_sync_fetched_count: int
    latest_sync_new_count: int
    latest_sync_updated_count: int


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def _extract_backfill_values(raw_payload: str | None) -> tuple[str, str, str, str]:
    if not raw_payload:
        return "", "", "", ""

    try:
        payload = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError):
        return "", "", "", ""

    detail_fields = payload.get("detail_fields")
    if not isinstance(detail_fields, dict):
        return "", "", "", ""

    location = str(detail_fields.get("Location", "") or "").strip()
    estimated_value = (
        str(
            detail_fields.get("Tender Value in ₹", "")
            or detail_fields.get("Tender Value", "")
            or ""
        ).strip()
    )
    searchable_text = " ".join(
        str(part).strip() for part in [*detail_fields.keys(), *detail_fields.values()] if part
    )
    emd_match = re.search(
        r"EMD Amount in (?:₹|Rs\.?)?\s*([0-9][0-9,]*(?:\.\d+)?)",
        searchable_text,
        re.I,
    )
    emd = emd_match.group(1).strip() if emd_match else ""
    description = (
        str(
            detail_fields.get("Name of Work / Subwork / Packages", "")
            or detail_fields.get("Work Description", "")
            or detail_fields.get("Title", "")
            or ""
        ).strip()
    )
    return location, emd, estimated_value, description


def get_connection(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=30, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    _configure_journal_mode(connection)
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def _configure_journal_mode(connection: sqlite3.Connection) -> str:
    last_error: sqlite3.Error | None = None
    for mode in PREFERRED_JOURNAL_MODES:
        try:
            row = connection.execute(f"PRAGMA journal_mode = {mode}").fetchone()
        except sqlite3.Error as exc:
            last_error = exc
            continue
        if row and str(row[0]).lower() == mode.lower():
            return str(row[0])
    if last_error is not None:
        raise last_error
    raise sqlite3.OperationalError("Unable to configure a supported SQLite journal mode.")


def init_db(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tenders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_tender_id TEXT,
                fingerprint TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                reference_no TEXT,
                department TEXT,
                location TEXT,
                emd TEXT,
                estimated_value TEXT,
                closing_date TEXT,
                closing_date_iso TEXT,
                bid_opening_date TEXT,
                bid_opening_date_iso TEXT,
                source_url TEXT NOT NULL,
                raw_payload TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tenders_closing_date_iso
            ON tenders(closing_date_iso);

            CREATE INDEX IF NOT EXISTS idx_tenders_updated_at
            ON tenders(updated_at);

            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_started_at TEXT NOT NULL,
                run_finished_at TEXT NOT NULL,
                status TEXT NOT NULL,
                fetched_count INTEGER NOT NULL DEFAULT 0,
                new_count INTEGER NOT NULL DEFAULT 0,
                updated_count INTEGER NOT NULL DEFAULT 0,
                message TEXT
            );
            """
        )


def quick_check_database(database_path: Path) -> None:
    if not database_path.exists():
        return

    with get_connection(database_path) as connection:
        row = connection.execute("PRAGMA quick_check").fetchone()
        status = row[0] if row else None
        if status != "ok":
            raise sqlite3.DatabaseError(f"SQLite quick_check failed: {status}")


def _backup_database_sidecar(path: Path, target: Path) -> None:
    if not path.exists():
        return
    shutil.move(str(path), str(target))


def backup_database_files(database_path: Path) -> Path | None:
    if not database_path.exists():
        return None

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    backup_path = database_path.with_name(
        f"{database_path.stem}.corrupt_{timestamp}{database_path.suffix}"
    )
    shutil.move(str(database_path), str(backup_path))

    for suffix in ("-journal", "-wal", "-shm"):
        _backup_database_sidecar(
            database_path.with_name(f"{database_path.name}{suffix}"),
            backup_path.with_name(f"{backup_path.name}{suffix}"),
        )

    return backup_path


def ensure_database_ready(database_path: Path) -> str | None:
    try:
        init_db(database_path)
        quick_check_database(database_path)
        normalize_existing_tenders(database_path)
        return None
    except sqlite3.Error as exc:
        backup_path = backup_database_files(database_path)
        init_db(database_path)
        message = "Recovered from a damaged SQLite database by creating a fresh file."
        if backup_path is not None:
            return (
                f"{message} Previous file backed up as `{backup_path.name}`. "
                f"Original error: {exc}"
            )
        return f"{message} Original error: {exc}"


def normalize_existing_tenders(database_path: Path) -> None:
    with get_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, source, source_tender_id, title, closing_date, fingerprint
            FROM tenders
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()

        if not rows:
            return

        keep_by_fingerprint: dict[str, int] = {}
        ids_to_delete: list[int] = []
        updates: list[tuple[str, str, int]] = []

        for row in rows:
            normalized_title = normalize_tender_title(row["title"])
            stable_fingerprint = build_fingerprint(
                {
                    "source": row["source"],
                    "source_tender_id": row["source_tender_id"],
                    "title": normalized_title,
                    "closing_date": row["closing_date"],
                }
            )
            if stable_fingerprint in keep_by_fingerprint:
                ids_to_delete.append(row["id"])
                continue
            keep_by_fingerprint[stable_fingerprint] = row["id"]
            if row["fingerprint"] != stable_fingerprint or row["title"] != normalized_title:
                updates.append((stable_fingerprint, normalized_title, row["id"]))

        if ids_to_delete:
            placeholders = ",".join("?" for _ in ids_to_delete)
            connection.execute(
                f"DELETE FROM tenders WHERE id IN ({placeholders})",
                ids_to_delete,
            )

        if updates:
            connection.executemany(
                "UPDATE tenders SET fingerprint = ?, title = ? WHERE id = ?",
                updates,
            )


def _existing_fingerprints(
    connection: sqlite3.Connection,
    fingerprints: list[str],
) -> set[str]:
    if not fingerprints:
        return set()

    placeholders = ",".join("?" for _ in fingerprints)
    query = f"SELECT fingerprint FROM tenders WHERE fingerprint IN ({placeholders})"
    rows = connection.execute(query, fingerprints).fetchall()
    return {row["fingerprint"] for row in rows}


def upsert_tenders(database_path: Path, tenders: Iterable[dict]) -> tuple[int, int]:
    deduplicated: dict[str, dict] = {}
    for tender in tenders:
        deduplicated[tender["fingerprint"]] = tender

    records = list(deduplicated.values())
    if not records:
        return 0, 0

    with get_connection(database_path) as connection:
        existing = _existing_fingerprints(
            connection, [record["fingerprint"] for record in records]
        )
        now = utc_now_iso()
        connection.executemany(
            """
            INSERT INTO tenders (
                source,
                source_tender_id,
                fingerprint,
                title,
                description,
                reference_no,
                department,
                location,
                emd,
                estimated_value,
                closing_date,
                closing_date_iso,
                bid_opening_date,
                bid_opening_date_iso,
                source_url,
                raw_payload,
                created_at,
                updated_at,
                last_seen_at
            ) VALUES (
                :source,
                :source_tender_id,
                :fingerprint,
                :title,
                :description,
                :reference_no,
                :department,
                :location,
                :emd,
                :estimated_value,
                :closing_date,
                :closing_date_iso,
                :bid_opening_date,
                :bid_opening_date_iso,
                :source_url,
                :raw_payload,
                :created_at,
                :updated_at,
                :last_seen_at
            )
            ON CONFLICT(fingerprint) DO UPDATE SET
                source = excluded.source,
                source_tender_id = excluded.source_tender_id,
                title = excluded.title,
                description = excluded.description,
                reference_no = excluded.reference_no,
                department = excluded.department,
                location = excluded.location,
                emd = excluded.emd,
                estimated_value = excluded.estimated_value,
                closing_date = excluded.closing_date,
                closing_date_iso = excluded.closing_date_iso,
                bid_opening_date = excluded.bid_opening_date,
                bid_opening_date_iso = excluded.bid_opening_date_iso,
                source_url = excluded.source_url,
                raw_payload = excluded.raw_payload,
                updated_at = excluded.updated_at,
                last_seen_at = excluded.last_seen_at
            """,
            [
                {
                    **record,
                    "raw_payload": json.dumps(record["raw_payload"], ensure_ascii=True),
                    "created_at": now,
                    "updated_at": now,
                    "last_seen_at": now,
                }
                for record in records
            ],
        )

    new_count = sum(1 for record in records if record["fingerprint"] not in existing)
    updated_count = len(records) - new_count
    return new_count, updated_count


def record_sync_run(
    database_path: Path,
    *,
    status: str,
    fetched_count: int,
    new_count: int,
    updated_count: int,
    message: str | None,
    started_at: str,
    finished_at: str,
) -> None:
    with get_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO sync_history (
                run_started_at,
                run_finished_at,
                status,
                fetched_count,
                new_count,
                updated_count,
                message
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_at,
                finished_at,
                status,
                fetched_count,
                new_count,
                updated_count,
                message,
            ),
        )


def fetch_tenders_dataframe(database_path: Path) -> pd.DataFrame:
    with get_connection(database_path) as connection:
        dataframe = pd.read_sql_query(
            """
            SELECT *
            FROM tenders
            ORDER BY
                CASE WHEN closing_date_iso IS NULL OR closing_date_iso = '' THEN 1 ELSE 0 END,
                closing_date_iso ASC,
                updated_at DESC
            """,
            connection,
        )

    if dataframe.empty:
        return dataframe

    if "raw_payload" in dataframe.columns:
        backfilled = dataframe["raw_payload"].apply(_extract_backfill_values)
        dataframe["_backfill_location"] = backfilled.str[0]
        dataframe["_backfill_emd"] = backfilled.str[1]
        dataframe["_backfill_estimated_value"] = backfilled.str[2]
        dataframe["_backfill_description"] = backfilled.str[3]

        for column, fallback_column in (
            ("location", "_backfill_location"),
            ("emd", "_backfill_emd"),
            ("estimated_value", "_backfill_estimated_value"),
            ("description", "_backfill_description"),
        ):
            if column not in dataframe.columns:
                dataframe[column] = dataframe[fallback_column]
                continue
            dataframe[column] = dataframe[column].fillna("")
            blank_mask = dataframe[column].str.strip() == ""
            dataframe.loc[blank_mask, column] = dataframe.loc[blank_mask, fallback_column]

        dataframe = dataframe.drop(
            columns=[
                "_backfill_location",
                "_backfill_emd",
                "_backfill_estimated_value",
                "_backfill_description",
            ]
        )

    dataframe["closing_date_sort"] = pd.to_datetime(
        dataframe["closing_date_iso"], errors="coerce", utc=True
    )
    dataframe["bid_opening_date_sort"] = pd.to_datetime(
        dataframe["bid_opening_date_iso"], errors="coerce", utc=True
    )
    return dataframe


def get_last_successful_sync_at(database_path: Path) -> str | None:
    with get_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT run_finished_at
            FROM sync_history
            WHERE status = 'success'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    return row["run_finished_at"] if row else None


def get_latest_sync_row(database_path: Path) -> sqlite3.Row | None:
    with get_connection(database_path) as connection:
        return connection.execute(
            """
            SELECT *
            FROM sync_history
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()


def get_latest_sync_finished_at(database_path: Path) -> str | None:
    latest_row = get_latest_sync_row(database_path)
    return latest_row["run_finished_at"] if latest_row else None


def get_sync_snapshot(database_path: Path) -> SyncSnapshot:
    latest_row = get_latest_sync_row(database_path)
    with get_connection(database_path) as connection:
        total_tenders = connection.execute("SELECT COUNT(*) AS count FROM tenders").fetchone()[
            "count"
        ]

    return SyncSnapshot(
        total_tenders=total_tenders,
        last_successful_sync_at=get_last_successful_sync_at(database_path),
        latest_sync_status=latest_row["status"] if latest_row else None,
        latest_sync_message=latest_row["message"] if latest_row else None,
        latest_sync_fetched_count=latest_row["fetched_count"] if latest_row else 0,
        latest_sync_new_count=latest_row["new_count"] if latest_row else 0,
        latest_sync_updated_count=latest_row["updated_count"] if latest_row else 0,
    )
