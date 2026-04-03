import unittest
from pathlib import Path

from tender_tracker.config import AppConfig
from tender_tracker.db import SyncSnapshot
from tender_tracker.services import SyncResult
from tender_tracker.ui import _format_timestamp, _refresh_snapshot_after_sync


class UiTests(unittest.TestCase):
    def _config(self) -> AppConfig:
        return AppConfig(
            project_root=Path.cwd(),
            database_path=Path("tests_tmp") / "ui_snapshot_test.db",
            source_url="https://example.com",
            source_name="CPPP",
            display_timezone="Asia/Kolkata",
            request_timeout_seconds=20,
            sync_interval_minutes=30,
            auto_refresh_seconds=300,
            max_scraped_tenders=25,
            auth_username="user",
            auth_password_hash="hash",
            auth_password_salt="salt",
            auth_iterations=390000,
        )

    def _snapshot(self, timestamp: str | None) -> SyncSnapshot:
        return SyncSnapshot(
            total_tenders=10,
            last_successful_sync_at=timestamp,
            latest_sync_status="success",
            latest_sync_message=None,
            latest_sync_fetched_count=10,
            latest_sync_new_count=1,
            latest_sync_updated_count=0,
        )

    def test_format_timestamp_converts_utc_to_ist(self) -> None:
        formatted = _format_timestamp("2026-04-03T02:24:00+00:00", "Asia/Kolkata")
        self.assertEqual(formatted, "03 Apr 2026 07:54 AM IST")

    def test_format_timestamp_treats_naive_values_as_utc(self) -> None:
        formatted = _format_timestamp("2026-04-03T02:24:00", "Asia/Kolkata")
        self.assertEqual(formatted, "03 Apr 2026 07:54 AM IST")

    def test_refresh_snapshot_after_sync_returns_latest_database_snapshot(self) -> None:
        initial_snapshot = self._snapshot("2026-04-03T02:10:00+00:00")
        refreshed_snapshot = self._snapshot("2026-04-03T02:24:00+00:00")
        result = SyncResult(attempted=True, performed=True, success=True)

        from unittest.mock import patch

        with patch("tender_tracker.ui.get_sync_snapshot", return_value=refreshed_snapshot) as mocked:
            current_snapshot = _refresh_snapshot_after_sync(self._config(), initial_snapshot, result)

        self.assertIs(current_snapshot, refreshed_snapshot)
        mocked.assert_called_once()

    def test_refresh_snapshot_without_new_sync_keeps_existing_snapshot(self) -> None:
        snapshot = self._snapshot("2026-04-03T02:10:00+00:00")
        result = SyncResult(attempted=False, performed=False, success=True)

        from unittest.mock import patch

        with patch("tender_tracker.ui.get_sync_snapshot") as mocked:
            current_snapshot = _refresh_snapshot_after_sync(self._config(), snapshot, result)

        self.assertIs(current_snapshot, snapshot)
        mocked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
