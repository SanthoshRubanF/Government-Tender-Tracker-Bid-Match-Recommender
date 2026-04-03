from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests
import sqlite3

from tender_tracker.config import AppConfig
from tender_tracker.db import (
    ensure_database_ready,
    get_latest_sync_finished_at,
    get_last_successful_sync_at,
    record_sync_run,
    upsert_tenders,
    utc_now_iso,
)
from tender_tracker.scraper import ScraperError, fetch_latest_tenders


UTC = timezone.utc


@dataclass
class SyncResult:
    attempted: bool
    performed: bool
    success: bool
    fetched_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    message: str | None = None


def _friendly_sync_message(exc: Exception) -> str:
    if isinstance(exc, requests.exceptions.ProxyError):
        return (
            "Automatic sync could not reach CPPP because the current proxy settings "
            "blocked the request. Cached tender data is still available."
        )
    if isinstance(exc, requests.exceptions.Timeout):
        return "Automatic sync timed out while contacting CPPP. Cached tender data is still available."
    if isinstance(exc, requests.exceptions.RequestException):
        return "Automatic sync could not reach CPPP right now. Cached tender data is still available."
    if isinstance(exc, sqlite3.Error):
        return f"Automatic sync could not write to the local database: {exc}"
    return str(exc)


def _record_sync_run_safe(**kwargs) -> str | None:
    try:
        record_sync_run(**kwargs)
        return None
    except sqlite3.Error as exc:
        return str(exc)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def is_sync_due(config: AppConfig) -> bool:
    latest_success = _parse_iso_datetime(get_last_successful_sync_at(config.database_path))
    latest_attempt = _parse_iso_datetime(get_latest_sync_finished_at(config.database_path))
    reference_time = latest_attempt or latest_success
    if reference_time is None:
        return True
    next_sync_due = reference_time + timedelta(minutes=config.sync_interval_minutes)
    return datetime.now(tz=UTC) >= next_sync_due


def sync_tenders(config: AppConfig, *, force: bool = False) -> SyncResult:
    ensure_database_ready(config.database_path)

    if not force and not is_sync_due(config):
        return SyncResult(
            attempted=False,
            performed=False,
            success=True,
            message="Sync skipped because the latest successful run is still fresh.",
        )

    started_at = utc_now_iso()
    try:
        tenders = fetch_latest_tenders(config)
        new_count, updated_count = upsert_tenders(config.database_path, tenders)
        finished_at = utc_now_iso()
        message = (
            f"Fetched {len(tenders)} tender rows from {config.source_name} "
            f"and stored {new_count} new rows."
        )
        history_error = _record_sync_run_safe(
            database_path=config.database_path,
            status="success",
            fetched_count=len(tenders),
            new_count=new_count,
            updated_count=updated_count,
            message=message,
            started_at=started_at,
            finished_at=finished_at,
        )
        if history_error:
            message = f"{message} Sync history write failed: {history_error}"
        return SyncResult(
            attempted=True,
            performed=True,
            success=True,
            fetched_count=len(tenders),
            new_count=new_count,
            updated_count=updated_count,
            message=message,
        )
    except (ScraperError, requests.RequestException, sqlite3.Error, OSError, ValueError) as exc:
        finished_at = utc_now_iso()
        message = _friendly_sync_message(exc)
        history_error = _record_sync_run_safe(
            database_path=config.database_path,
            status="error",
            fetched_count=0,
            new_count=0,
            updated_count=0,
            message=message,
            started_at=started_at,
            finished_at=finished_at,
        )
        if history_error:
            message = f"{message} Sync history write failed: {history_error}"
        return SyncResult(
            attempted=True,
            performed=True,
            success=False,
            message=message,
        )
