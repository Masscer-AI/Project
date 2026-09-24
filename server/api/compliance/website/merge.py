from __future__ import annotations

import re

_COMPANY_KEYS = (
    "legal_name",
    "nationality",
    "economic_activity",
    "email",
    "phone",
)
_DIGITS_RE = re.compile(r"[^\d]")


def _blank(value) -> bool:
    return not str(value or "").strip()


def normalize_extracted_phone(raw: str | None) -> str | None:
    digits = _DIGITS_RE.sub("", raw or "")
    if len(digits) < 7:
        return None
    return f"+{digits}"


def normalize_extracted_nationality(raw: str | None) -> str | None:
    code = (raw or "").strip().upper()
    if len(code) == 2 and code.isalpha():
        return code
    return None


def merge_website_fields(current: dict, extracted) -> dict:
    out = dict(current or {})
    payload = extracted if isinstance(extracted, dict) else extracted.model_dump()
    for key in _COMPANY_KEYS:
        if not _blank(out.get(key)):
            continue
        value = payload.get(key)
        if key == "phone":
            value = normalize_extracted_phone(value if isinstance(value, str) else None)
        elif key == "nationality":
            value = normalize_extracted_nationality(
                value if isinstance(value, str) else None
            )
        elif isinstance(value, str):
            value = value.strip() or None
        if value:
            out[key] = value
    return out
