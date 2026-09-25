from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

_DIGITS_RE = re.compile(r"[^\d]")
_NAME_RE = re.compile(
    r"^(?:"
    r"legal_name|constitution_date|nationality|rfc|economic_activity|phone|email|"
    r"given_names|surnames|date_of_birth|country_of_birth|curp|"
    r"address\.(?:street|exterior_number|interior_number|neighborhood|"
    r"municipality|city|state|postal_code|country)|"
    r"identification\.(?:document_type|issuing_authority|document_number)|"
    r"representative\.(?:given_names|surnames|date_of_birth|rfc|curp|"
    r"identification\.(?:document_type|issuing_authority|document_number))|"
    r"controller\.(?:name|rfc|ownership_percentage|email)|"
    r"controllers\.\d+\.(?:name|rfc|ownership_percentage|email)"
    r")$"
)


class FillFormVariableParams(BaseModel):
    name: str = Field(description="Form field path, e.g. legal_name or address.country.")
    value: str = Field(description="Value visible on the document.")


class FillFormVariableResult(BaseModel):
    name: str
    filled: bool
    message: str = ""


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, dict):
        return all(_blank(item) for item in value.values())
    if isinstance(value, list):
        return all(_blank(item) for item in value)
    return False


def _get_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if current is None:
            return None
        if part.isdigit():
            idx = int(part)
            if not isinstance(current, list) or idx >= len(current):
                return None
            current = current[idx]
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _set_path(data: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    current: Any = data
    for i, part in enumerate(parts[:-1]):
        nxt = parts[i + 1]
        if part.isdigit():
            idx = int(part)
            while len(current) <= idx:
                current.append({})
            if not isinstance(current[idx], dict):
                current[idx] = {}
            current = current[idx]
            continue
        if nxt.isdigit():
            child = current.get(part)
            if not isinstance(child, list):
                child = []
                current[part] = child
            current = child
            continue
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    last = parts[-1]
    if last.isdigit():
        idx = int(last)
        while len(current) <= idx:
            current.append(None)
        current[idx] = value
        return
    current[last] = value


def _normalize_value(name: str, raw: str) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    leaf = name.split(".")[-1]
    if leaf in {"nationality", "country", "country_of_birth"}:
        code = text.upper()
        if len(code) == 2 and code.isalpha():
            return code
        return None
    if leaf == "phone":
        digits = _DIGITS_RE.sub("", text)
        if len(digits) < 7:
            return None
        return f"+{digits}"
    if leaf == "document_type":
        from api.compliance.document_extraction.schemas import canonical_id_type

        return canonical_id_type(text)
    if leaf == "document_number":
        half = len(text) // 2
        if half and text[:half] == text[half:]:
            return text[:half]
    return text


def allowed_form_names() -> list[str]:
    return [
        "legal_name",
        "constitution_date",
        "nationality",
        "rfc",
        "economic_activity",
        "phone",
        "email",
        "given_names",
        "surnames",
        "date_of_birth",
        "country_of_birth",
        "curp",
        "address.street",
        "address.exterior_number",
        "address.interior_number",
        "address.neighborhood",
        "address.municipality",
        "address.city",
        "address.state",
        "address.postal_code",
        "address.country",
        "identification.document_type",
        "identification.issuing_authority",
        "identification.document_number",
        "representative.given_names",
        "representative.surnames",
        "representative.date_of_birth",
        "representative.rfc",
        "representative.curp",
        "representative.identification.document_type",
        "representative.identification.issuing_authority",
        "representative.identification.document_number",
        "controllers.0.name",
        "controllers.0.rfc",
        "controllers.0.ownership_percentage",
        "controllers.0.email",
    ]


def form_field_snapshot(metadata: dict | None) -> tuple[dict[str, str], list[str]]:
    meta = metadata if isinstance(metadata, dict) else {}
    filled: dict[str, str] = {}
    empty: list[str] = []
    for name in allowed_form_names():
        current = _get_path(meta, name)
        if _blank(current):
            empty.append(name)
        else:
            filled[name] = str(current).strip()
    return filled, empty


def fill_form_variable_impl(entity, name: str, value: str) -> FillFormVariableResult:
    from api.compliance.pld_metadata import normalize_pld_entity_metadata

    key = (name or "").strip()
    if not _NAME_RE.match(key):
        return FillFormVariableResult(name=key, filled=False, message="unknown field")
    normalized = _normalize_value(key, value)
    if not normalized:
        return FillFormVariableResult(name=key, filled=False, message="empty value")
    entity.refresh_from_db()
    meta = dict(entity.metadata or {})
    current = _get_path(meta, key)
    if not _blank(current) and str(current).strip() == normalized:
        return FillFormVariableResult(name=key, filled=False, message="unchanged")
    _set_path(meta, key, normalized)
    try:
        entity.metadata = normalize_pld_entity_metadata(entity.person_type, meta)
        entity.save(update_fields=["metadata", "updated_at"])
    except (ValueError, TypeError) as exc:
        return FillFormVariableResult(name=key, filled=False, message=str(exc))
    return FillFormVariableResult(name=key, filled=True, message="ok")


def _text(value) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _representative_id_pairs(payload: dict) -> list[tuple[str, str | None]]:
    from api.compliance.document_extraction.schemas import canonical_id_type

    document_type = canonical_id_type(payload.get("document_subtype"))
    number = _text(payload.get("document_number")) or _text(payload.get("cic"))
    return [
        ("representative.given_names", _text(payload.get("given_names"))),
        ("representative.surnames", _text(payload.get("surnames"))),
        ("representative.date_of_birth", _text(payload.get("date_of_birth"))),
        ("representative.identification.document_type", document_type),
        ("representative.identification.document_number", number),
        (
            "representative.identification.issuing_authority",
            "INE" if document_type == "ine" else None,
        ),
    ]


def _representative_curp_pairs(payload: dict) -> list[tuple[str, str | None]]:
    return [
        ("representative.given_names", _text(payload.get("given_names"))),
        ("representative.surnames", _text(payload.get("surnames"))),
        ("representative.date_of_birth", _text(payload.get("date_of_birth"))),
        ("representative.curp", _text(payload.get("curp"))),
    ]


def apply_extraction_to_form(entity, kind: str, payload: dict) -> None:
    if not isinstance(payload, dict):
        return
    if kind == "id_representante":
        pairs = _representative_id_pairs(payload)
    elif kind == "curp_representante":
        pairs = _representative_curp_pairs(payload)
    elif kind == "acta_constitutiva":
        pairs = [
            ("legal_name", payload.get("legal_name")),
            ("constitution_date", payload.get("constitution_date")),
            ("rfc", payload.get("rfc")),
            ("economic_activity", payload.get("corporate_purpose")),
        ]
        address = payload.get("registered_address")
        if isinstance(address, dict):
            pairs.append(("nationality", address.get("country")))
            for field in (
                "street",
                "exterior_number",
                "interior_number",
                "neighborhood",
                "municipality",
                "city",
                "state",
                "postal_code",
                "country",
            ):
                pairs.append((f"address.{field}", address.get(field)))
        shareholders = payload.get("shareholders")
        if isinstance(shareholders, list):
            for index, row in enumerate(shareholders[:5]):
                if not isinstance(row, dict):
                    continue
                pairs.append((f"controllers.{index}.name", row.get("name")))
                pairs.append((f"controllers.{index}.rfc", row.get("rfc")))
                pairs.append(
                    (
                        f"controllers.{index}.ownership_percentage",
                        row.get("ownership_percentage"),
                    )
                )
    else:
        return
    for name, raw in pairs:
        if isinstance(raw, str) and raw.strip():
            fill_form_variable_impl(entity, name, raw)


def form_fill_prompt(entity) -> str:
    filled, empty = form_field_snapshot(getattr(entity, "metadata", None))
    return (
        "Current identification form state.\n"
        f"Filled: {json.dumps(filled, ensure_ascii=False)}\n"
        f"Empty: {json.dumps(empty)}\n"
        "Call fill_form_variable for empty fields the document shows. "
        "If a filled field disagrees with the document, call fill_form_variable "
        "with the document value. Do not invent RFC, dates, or addresses."
    )


def make_fill_form_variable_tool(entity) -> dict:
    def fill_form_variable(name: str, value: str) -> FillFormVariableResult:
        return fill_form_variable_impl(entity, name, value)

    return {
        "name": "fill_form_variable",
        "description": (
            "Write one identification-form field from the document. "
            "Use this for empty fields and to correct a value that disagrees "
            "with the document. Paths such as legal_name, constitution_date, "
            "nationality, or address.country."
        ),
        "parameters": FillFormVariableParams,
        "function": fill_form_variable,
    }
