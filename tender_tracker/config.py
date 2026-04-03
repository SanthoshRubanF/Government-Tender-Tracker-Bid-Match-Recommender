from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SOURCE_URL = (
    "https://www.etenders.gov.in/eprocure/app"
    "?component=%24DirectLink&page=P"
)


def _read_secret(name: str, default: Any = None) -> Any:
    try:
        import streamlit as st

        return st.secrets.get(name, default)
    except Exception:
        return default


def _read_setting(name: str, default: Any = None) -> Any:
    return os.getenv(name, _read_secret(name, default))


def _read_int(name: str, default: int) -> int:
    value = _read_setting(name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    database_path: Path
    source_url: str
    source_name: str
    request_timeout_seconds: int
    sync_interval_minutes: int
    auto_refresh_seconds: int
    max_scraped_tenders: int
    auth_username: str
    auth_password_hash: str
    auth_password_salt: str
    auth_iterations: int


def load_config(project_root: Path | None = None) -> AppConfig:
    root = (project_root or Path.cwd()).resolve()
    database_name = _read_setting("TENDER_TRACKER_DB_PATH", "tenders.db")
    database_path = (root / database_name).resolve()

    return AppConfig(
        project_root=root,
        database_path=database_path,
        source_url=_read_setting("TENDER_TRACKER_SOURCE_URL", DEFAULT_SOURCE_URL),
        source_name=_read_setting("TENDER_TRACKER_SOURCE_NAME", "CPPP"),
        request_timeout_seconds=_read_int("TENDER_TRACKER_REQUEST_TIMEOUT", 20),
        sync_interval_minutes=_read_int("TENDER_TRACKER_SYNC_INTERVAL_MINUTES", 30),
        auto_refresh_seconds=_read_int("TENDER_TRACKER_AUTO_REFRESH_SECONDS", 300),
        max_scraped_tenders=_read_int("TENDER_TRACKER_MAX_TENDERS", 25),
        auth_username=str(_read_setting("TENDER_TRACKER_USERNAME", "")),
        auth_password_hash=str(_read_setting("TENDER_TRACKER_PASSWORD_HASH", "")),
        auth_password_salt=str(_read_setting("TENDER_TRACKER_PASSWORD_SALT", "")),
        auth_iterations=_read_int("TENDER_TRACKER_PASSWORD_ITERATIONS", 390000),
    )
