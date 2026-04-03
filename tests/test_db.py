import unittest
from pathlib import Path
import uuid

from tender_tracker.db import fetch_tenders_dataframe, get_connection, init_db, upsert_tenders


class DatabaseTests(unittest.TestCase):
    def _database_path(self) -> Path:
        return Path("tests_tmp") / f"db_case_{uuid.uuid4().hex}" / "tenders.db"

    def test_init_db_uses_a_supported_journal_mode_for_fresh_databases(self) -> None:
        database_path = self._database_path()
        init_db(database_path)

        with get_connection(database_path) as connection:
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

        self.assertIn(str(journal_mode).lower(), {"wal", "truncate", "persist", "memory", "off"})

    def test_upsert_tenders_deduplicates_by_fingerprint(self) -> None:
        database_path = self._database_path()
        init_db(database_path)

        tender = {
            "source": "CPPP",
            "source_tender_id": "ABC-123",
            "fingerprint": "fingerprint-1",
            "title": "Road construction",
            "description": "Civil works package",
            "reference_no": "ABC-123",
            "department": "PWD",
            "location": "Madurai",
            "emd": "",
            "estimated_value": "",
            "closing_date": "09-Apr-2026 03:30 PM",
            "closing_date_iso": "2026-04-09T15:30:00",
            "bid_opening_date": "10-Apr-2026 03:30 PM",
            "bid_opening_date_iso": "2026-04-10T15:30:00",
            "source_url": "https://example.com/tender",
            "raw_payload": {"title": "Road construction"},
        }

        new_count, updated_count = upsert_tenders(database_path, [tender])
        self.assertEqual((new_count, updated_count), (1, 0))

        tender["title"] = "Road construction updated"
        new_count, updated_count = upsert_tenders(database_path, [tender])
        self.assertEqual((new_count, updated_count), (0, 1))

        dataframe = fetch_tenders_dataframe(database_path)
        self.assertEqual(len(dataframe), 1)
        self.assertEqual(dataframe.iloc[0]["title"], "Road construction updated")

    def test_fetch_tenders_dataframe_backfills_export_fields_from_raw_payload(self) -> None:
        database_path = self._database_path()
        init_db(database_path)

        tender = {
            "source": "CPPP",
            "source_tender_id": "ABC-456",
            "fingerprint": "fingerprint-2",
            "title": "Electrical maintenance",
            "description": "",
            "reference_no": "ABC-456",
            "department": "Electrical",
            "location": "",
            "emd": "",
            "estimated_value": "",
            "closing_date": "09-Apr-2026 03:30 PM",
            "closing_date_iso": "2026-04-09T15:30:00",
            "bid_opening_date": "10-Apr-2026 03:30 PM",
            "bid_opening_date_iso": "2026-04-10T15:30:00",
            "source_url": "https://example.com/tender",
            "raw_payload": {
                "detail_fields": {
                    "Location": "Coimbatore",
                    "Tender Value in ₹": "12,50,000",
                    "Work Description": "Repair and maintenance work",
                    (
                        "Cover Type Description EMD Fee Details "
                        "EMD Amount in ₹ 25,000 EMD Exemption Allowed No"
                    ): "Supporting document",
                }
            },
        }

        upsert_tenders(database_path, [tender])
        dataframe = fetch_tenders_dataframe(database_path)

        self.assertEqual(dataframe.iloc[0]["location"], "Coimbatore")
        self.assertEqual(dataframe.iloc[0]["emd"], "25,000")
        self.assertEqual(dataframe.iloc[0]["estimated_value"], "12,50,000")
        self.assertEqual(dataframe.iloc[0]["description"], "Repair and maintenance work")


if __name__ == "__main__":
    unittest.main()
