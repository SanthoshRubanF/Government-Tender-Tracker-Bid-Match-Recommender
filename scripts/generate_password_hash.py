from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tender_tracker.auth import generate_salt, hash_password


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a password hash for Tender Tracker secrets."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=390000,
        help="PBKDF2 iteration count to embed in your secrets.",
    )
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirm_password = getpass.getpass("Confirm password: ")
    if password != confirm_password:
        raise SystemExit("Passwords did not match.")

    salt = generate_salt()
    password_hash = hash_password(password, salt, args.iterations)

    print("Add these values to .streamlit/secrets.toml or your environment:")
    print('TENDER_TRACKER_USERNAME = "admin"')
    print(f'TENDER_TRACKER_PASSWORD_HASH = "{password_hash}"')
    print(f'TENDER_TRACKER_PASSWORD_SALT = "{salt}"')
    print(f"TENDER_TRACKER_PASSWORD_ITERATIONS = {args.iterations}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
