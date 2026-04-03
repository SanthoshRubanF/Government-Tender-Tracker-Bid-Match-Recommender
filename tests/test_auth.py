import unittest

from tender_tracker.auth import generate_salt, hash_password, verify_password


class AuthTests(unittest.TestCase):
    def test_hash_and_verify_password(self) -> None:
        salt = generate_salt()
        password_hash = hash_password("super-secret-password", salt, 1000)

        self.assertTrue(
            verify_password("super-secret-password", password_hash, salt, 1000)
        )
        self.assertFalse(verify_password("wrong-password", password_hash, salt, 1000))


if __name__ == "__main__":
    unittest.main()
