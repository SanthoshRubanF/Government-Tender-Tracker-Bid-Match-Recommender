from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from tender_tracker.config import AppConfig


def generate_salt(length: int = 16) -> str:
    return secrets.token_hex(length)


def hash_password(password: str, salt: str, iterations: int = 390000) -> str:
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return base64.b64encode(derived_key).decode("ascii")


def verify_password(
    password: str,
    expected_hash: str,
    salt: str,
    iterations: int = 390000,
) -> bool:
    if not password or not expected_hash or not salt:
        return False
    calculated = hash_password(password, salt, iterations)
    return hmac.compare_digest(calculated, expected_hash)


def is_auth_configured(config: AppConfig) -> bool:
    return bool(
        config.auth_username
        and config.auth_password_hash
        and config.auth_password_salt
    )
