"""Copy provenance citations into empty schema fields when the model skipped them."""

from __future__ import annotations

import re
from typing import Any

from api.compliance.document_extraction.schemas import canonical_id_type
from api.compliance.document_extraction.spec_fields import (
    SPEC_FIELDS_BY_KIND,
    _is_filled,
    _path_value,
)

# Models sometimes cite pages with nested ids instead of ACTA-* / ID-* campo_ids.
PROVENANCE_FIELD_ALIASES: dict[str, str] = {
    "sociedad.razon_social": "legal_name",
    "sociedad.tipo_societario": "entity_type",
    "sociedad.fecha_constitucion": "constitution_date",
    "sociedad.rfc": "rfc",
    "sociedad.objeto_social": "corporate_purpose",
    "sociedad.duracion_anios": "duration",
    "sociedad.capital_social.tipo": "share_capital_kind",
    "sociedad.capital_social.monto": "share_capital_amount",
    "sociedad.domicilio_social": "registered_address",
    "documento.tipo_documento": "document_subtype",
}

_OFFICIAL_ID_ALIASES: dict[str, str] = {
    "tipo_identificacion": "document_subtype",
    "nombre_completo": "full_name",
    "fecha_nacimiento": "date_of_birth",
    "sexo": "sex",
    "domicilio": "address_text",
    "clave_elector": "citizen_identifier",
    "folio": "document_number",
    "cic": "cic",
    "idmex": "cic",
    "vigencia": "validity_year",
    "fecha_expedicion": "issue_date",
    "fecha_vencimiento": "expiry_date",
    "nacionalidad": "nationality",
    "curp": "curp",
}

_CURP_ALIASES: dict[str, str] = {
    "nombre": "full_name",
    "nombre_completo": "full_name",
    "fecha_nacimiento": "date_of_birth",
    "sexo": "sex",
    "entidad_registro": "entidad_nacimiento",
    "curp": "curp",
    "folio": "folio",
}

PROVENANCE_FIELD_ALIASES_BY_KIND: dict[str, dict[str, str]] = {
    "comprobante_domicilio": {
        "account_holder": "account_holder_name",
        "legal_name": "account_holder_name",
        "addresses": "service_address",
        "dates.issue_date": "issue_or_period_date",
        "dates.certification_date": "issue_or_period_date",
        "dates.billing_period": "issue_or_period_date",
        "dates": "issue_or_period_date",
        "billing_period": "issue_or_period_date",
    },
    "official_id": _OFFICIAL_ID_ALIASES,
    "id_representante": _OFFICIAL_ID_ALIASES,
    "id_controlador": _OFFICIAL_ID_ALIASES,
    "curp": _CURP_ALIASES,
    "curp_representante": _CURP_ALIASES,
}


def _set_path(payload: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    current: Any = payload
    for part in parts[:-1]:
        nxt = current.get(part)
        if nxt is None:
            current[part] = {}
            nxt = current[part]
        if not isinstance(nxt, dict):
            return
        current = nxt
    current[parts[-1]] = value


_IDMEX_RE = re.compile(r"IDMEX\s*(\d+)", re.I)
_CLAVE_ELECTOR_RE = re.compile(r"[A-Za-z]")


def _apply_ine_idmex(data: dict[str, Any]) -> bool:
    blobs = [data.get("mrz"), data.get("ocr_line"), data.get("document_number"), data.get("cic")]
    for row in data.get("provenances") or []:
        if isinstance(row, dict):
            blobs.append(row.get("texto_origen"))
            blobs.append(row.get("valor_extraido"))
    joined = " ".join(str(part) for part in blobs if part)
    match = _IDMEX_RE.search(re.sub(r"\s+", "", joined))
    ine = match.group(1) if match else None
    if not ine:
        cic = data.get("cic")
        if isinstance(cic, str) and cic.strip().isdigit():
            ine = cic.strip()
    if not ine:
        return False
    changed = False
    current = data.get("document_number")
    if (
        isinstance(current, str)
        and current
        and current != ine
        and _CLAVE_ELECTOR_RE.search(current)
        and not data.get("citizen_identifier")
    ):
        data["citizen_identifier"] = current
        changed = True
    if data.get("document_number") != ine:
        data["document_number"] = ine
        changed = True
    if data.get("cic") != ine:
        data["cic"] = ine
        changed = True
    return changed


def _drop_id_curp(data: dict[str, Any]) -> bool:
    changed = False
    if data.get("curp") is not None:
        data["curp"] = None
        changed = True
    rows = data.get("provenances") or []
    kept = [
        row
        for row in rows
        if not (
            isinstance(row, dict)
            and str(row.get("campo_id") or "").lower() in {"curp", "curp-curp"}
        )
    ]
    if len(kept) != len(rows):
        data["provenances"] = kept
        changed = True
    return changed


def _citation_value(row: dict[str, Any]) -> str | None:
    if row.get("estado_validacion") == "no_encontrado":
        return None
    for key in ("valor_extraido", "texto_origen"):
        raw = row.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        if raw is not None and not isinstance(raw, str):
            return str(raw)
    return None


def hydrate_extraction(parsed, document_kind: str):
    """Fill empty scalar schema fields from provenances. Lists are left as-is."""
    data = parsed.model_dump()
    provenances = data.get("provenances") or []
    by_campo = {
        row.get("campo_id"): row
        for row in provenances
        if isinstance(row, dict) and row.get("campo_id")
    }
    mapping = {
        **(SPEC_FIELDS_BY_KIND.get(document_kind) or {}),
        **PROVENANCE_FIELD_ALIASES,
        **(PROVENANCE_FIELD_ALIASES_BY_KIND.get(document_kind) or {}),
    }
    changed = False
    for campo_id, path in mapping.items():
        if path in {
            "shareholders",
            "administrators",
            "holders",
            "economic_activities",
            "tax_regimes",
        }:
            continue
        if path.endswith("_address") or path == "registered_address":
            if _is_filled(_path_value(data, f"{path}.raw_text")) or _is_filled(
                _path_value(data, path)
            ):
                continue
            row = by_campo.get(campo_id)
            if not isinstance(row, dict):
                continue
            value = _citation_value(row)
            if value:
                _set_path(data, f"{path}.raw_text", value)
                changed = True
            continue
        if _is_filled(_path_value(data, path)):
            continue
        row = by_campo.get(campo_id)
        if not isinstance(row, dict):
            continue
        value = _citation_value(row)
        if not value:
            continue
        if path == "document_subtype":
            value = canonical_id_type(value)
            if not value:
                continue
        _set_path(data, path, value)
        changed = True
    if document_kind in {"official_id", "id_representante", "id_controlador"}:
        if _apply_ine_idmex(data):
            changed = True
    if document_kind == "id_representante":
        if _drop_id_curp(data):
            changed = True
    if not changed:
        return parsed
    return parsed.__class__.model_validate(data)
