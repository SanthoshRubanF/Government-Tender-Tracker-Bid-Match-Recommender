import unittest

import pandas as pd

from tender_tracker.matcher import rank_tenders


class MatcherTests(unittest.TestCase):
    def test_rank_tenders_orders_more_relevant_items_first(self) -> None:
        dataframe = pd.DataFrame(
            [
                {
                    "title": "Road construction and bridge repair",
                    "description": "Civil works across the district.",
                    "reference_no": "RD-001",
                    "department": "PWD",
                    "location": "Madurai",
                    "updated_at": "2026-04-02T00:00:00+00:00",
                    "closing_date_sort": pd.Timestamp("2026-04-20T00:00:00+00:00"),
                },
                {
                    "title": "Medical imaging equipment procurement",
                    "description": "Hospital purchase of diagnostic machines.",
                    "reference_no": "MD-002",
                    "department": "Health",
                    "location": "Chennai",
                    "updated_at": "2026-04-02T00:00:00+00:00",
                    "closing_date_sort": pd.Timestamp("2026-04-10T00:00:00+00:00"),
                },
            ]
        )

        ranked = rank_tenders(
            "road construction civil works contractor bridge projects",
            dataframe,
            minimum_score=0.0,
        )

        self.assertEqual(ranked.iloc[0]["reference_no"], "RD-001")
        self.assertGreater(ranked.iloc[0]["match_score"], ranked.iloc[1]["match_score"])


if __name__ == "__main__":
    unittest.main()
