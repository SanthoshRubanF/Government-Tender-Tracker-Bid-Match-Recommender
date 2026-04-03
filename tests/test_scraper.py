import unittest

from tender_tracker.scraper import (
    _parse_latest_tender_rows,
    build_fingerprint,
    enrich_tender_from_detail_page,
    extract_detail_fields,
)


class _DummyResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _DummySession:
    def __init__(self, text: str) -> None:
        self._text = text

    def get(self, source_url: str, timeout: int) -> _DummyResponse:
        return _DummyResponse(self._text)


class ScraperTests(unittest.TestCase):
    def test_extract_detail_fields_reads_organisation_chain(self) -> None:
        html = """
        <table>
            <tr>
                <td class="td_caption"><b>Organisation Chain</b></td>
                <td class="td_field" colspan="5"><b>Ministry A||Department B||Office C</b></td>
            </tr>
            <tr>
                <td class="td_caption"><b>Tender Reference Number</b></td>
                <td class="td_field"><b>ABC-123</b></td>
            </tr>
        </table>
        """

        fields = extract_detail_fields(html)

        self.assertEqual(
            fields["Organisation Chain"],
            "Ministry A||Department B||Office C",
        )
        self.assertEqual(fields["Tender Reference Number"], "ABC-123")

    def test_parse_latest_tender_rows_extracts_expected_columns(self) -> None:
        rows = [
            [
                {"text": "Tender Title", "links": []},
                {"text": "Reference No", "links": []},
                {"text": "Closing Date", "links": []},
                {"text": "Bid Opening Date", "links": []},
            ],
            [
                {"text": "1", "links": []},
                {
                    "text": "Construction of retaining wall",
                    "links": ["/eprocure/app?component=view1"],
                },
                {"text": "NIT-22-2025-26", "links": []},
                {"text": "09-Apr-2026 03:30 PM", "links": []},
                {"text": "10-Apr-2026 03:30 PM", "links": []},
            ],
            [{"text": "Latest Tenders updates every 15 mins", "links": []}],
        ]

        tenders = _parse_latest_tender_rows(
            rows,
            base_url="https://www.etenders.gov.in/eprocure/app?component=%24DirectLink&page=P",
            source_name="CPPP",
            limit=25,
        )

        self.assertEqual(len(tenders), 1)
        self.assertEqual(tenders[0]["reference_no"], "NIT-22-2025-26")
        self.assertEqual(tenders[0]["title"], "Construction of retaining wall")
        self.assertTrue(tenders[0]["source_url"].startswith("https://www.etenders.gov.in"))

    def test_build_fingerprint_ignores_cppp_row_number_prefixes(self) -> None:
        base_tender = {
            "source": "CPPP",
            "source_tender_id": "ABC-123",
            "closing_date": "09-Apr-2026 03:30 PM",
        }

        left = build_fingerprint({**base_tender, "title": "1. Construction of retaining wall"})
        right = build_fingerprint({**base_tender, "title": "9. Construction of retaining wall"})

        self.assertEqual(left, right)

    def test_enrich_tender_from_detail_page_populates_export_fields(self) -> None:
        detail_html = """
        <table>
            <tr>
                <td class="td_caption"><b>Organisation Chain</b></td>
                <td class="td_field"><b>Department A</b></td>
            </tr>
            <tr>
                <td class="td_caption"><b>Cover Type</b></td>
                <td class="td_field">
                    EMD Fee Details EMD Amount in &#8377; 15,000 EMD Exemption Allowed No
                </td>
            </tr>
            <tr>
                <td class="td_caption"><b>Tender Value in &#8377;</b></td>
                <td class="td_field"><b>5,30,785</b></td>
            </tr>
            <tr>
                <td class="td_caption"><b>Location</b></td>
                <td class="td_field"><b>Kolkata</b></td>
            </tr>
            <tr>
                <td class="td_caption"><b>Work Description</b></td>
                <td class="td_field"><b>Supply and installation of cooling systems</b></td>
            </tr>
        </table>
        """
        tender = {
            "source_url": "https://example.com/tender",
            "department": "",
            "location": "",
            "emd": "",
            "estimated_value": "",
            "description": "",
            "raw_payload": {},
        }

        enriched = enrich_tender_from_detail_page(
            _DummySession(detail_html),
            tender,
            timeout_seconds=10,
        )

        self.assertEqual(enriched["department"], "Department A")
        self.assertEqual(enriched["location"], "Kolkata")
        self.assertEqual(enriched["emd"], "15,000")
        self.assertEqual(enriched["estimated_value"], "5,30,785")
        self.assertEqual(
            enriched["description"],
            "Supply and installation of cooling systems",
        )


if __name__ == "__main__":
    unittest.main()
