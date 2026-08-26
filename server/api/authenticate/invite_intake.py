"""Optional fields captured when inviting a client/supplier for compliance."""

from __future__ import annotations

import re

_KEY_RE = re.compile(r"[^a-z0-9_]")
_RESERVED_KEYS = {"email", "name", "bio"}
_MAX_KEY_LEN = 40
_MAX_VALUE_LEN = 500
_MAX_FIELDS = 30


def _clean_key(key) -> str:
    raw = str(key or "").strip().lower().replace(" ", "_")
    return _KEY_RE.sub("", raw)[:_MAX_KEY_LEN]


def _clean_value(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = str(value).strip()
    if not text:
        return None
    return text[:_MAX_VALUE_LEN]


def normalize_invite_intake(raw) -> dict:
    if raw is None or raw == "":
        return {}
    if not isinstance(raw, dict):
        raise ValueError("intake must be a JSON object")

    out: dict = {}
    for key, value in raw.items():
        cleaned_key = _clean_key(key)
        if not cleaned_key or cleaned_key in _RESERVED_KEYS:
            continue
        cleaned_val = _clean_value(value)
        if cleaned_val is None:
            continue
        if cleaned_key == "rfc" and isinstance(cleaned_val, str):
            cleaned_val = cleaned_val.upper().replace(" ", "")
        out[cleaned_key] = cleaned_val
        if len(out) >= _MAX_FIELDS:
            break
    return out
