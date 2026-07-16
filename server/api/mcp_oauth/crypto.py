"""Hashing helpers for OAuth secrets and tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_token(length: int = 48) -> str:
    return secrets.token_urlsafe(length)


def generate_client_id() -> str:
    return secrets.token_urlsafe(24)


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_secret(value: str, stored_hash: str) -> bool:
    if not value or not stored_hash:
        return False
    return hmac.compare_digest(hash_secret(value), stored_hash)
