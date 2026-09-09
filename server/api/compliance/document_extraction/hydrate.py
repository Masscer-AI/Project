"""Copy provenance citations into empty schema fields when the model skipped them."""

from __future__ import annotations

from typing import Any

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
        _set_path(data, path, value)
        changed = True
    if not changed:
        return parsed
    return parsed.__class__.model_validate(data)
