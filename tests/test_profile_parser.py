import io
import unittest

from tender_tracker.profile_parser import ProfileValidationError, load_profile_text


class NamedBytesIO(io.BytesIO):
    def __init__(self, data: bytes, name: str) -> None:
        super().__init__(data)
        self.name = name

    def getvalue(self) -> bytes:
        return super().getvalue()


class ProfileParserTests(unittest.TestCase):
    def test_loads_preferred_services_column(self) -> None:
        uploaded = NamedBytesIO(
            b"services,notes\nRoad construction,Experienced bidder\n",
            "profile.csv",
        )
        profile_text, details = load_profile_text(uploaded)

        self.assertIn("Road construction", profile_text)
        self.assertEqual(details["columns_used"], ["services"])

    def test_rejects_empty_csv(self) -> None:
        uploaded = NamedBytesIO(b"services\n", "empty.csv")

        with self.assertRaises(ProfileValidationError):
            load_profile_text(uploaded)


if __name__ == "__main__":
    unittest.main()
