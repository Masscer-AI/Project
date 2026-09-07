"""Spec campo_id coverage for identification documents currently collected."""

from __future__ import annotations

from typing import Any

# Maps document_kind -> spec campo_id -> dotted path in the extraction payload.
SPEC_FIELDS_BY_KIND: dict[str, dict[str, str]] = {
    "constancia_fiscal": {
        "CSF-rfc": "rfc",
        "CSF-nombre_razon_social": "legal_name_or_full_name",
        "CSF-tipo_persona": "person_kind",
        "CSF-regimen_fiscal": "tax_regimes",
        "CSF-domicilio_fiscal": "tax_address",
        "CSF-cp_fiscal": "postal_code",
        "CSF-actividades_economicas": "economic_activities",
        "CSF-fecha_inicio_operaciones": "operations_start_date",
        "CSF-estatus_padron": "padron_status",
        "CSF-fecha_emision": "issued_at",
    },
    "official_id": {
        "ID-tipo": "document_subtype",
        "ID-nombre_completo": "full_name",
        "ID-fecha_nacimiento": "date_of_birth",
        "ID-nacionalidad": "nationality",
        "ID-sexo": "sex",
        "ID-domicilio": "address_text",
        "ID-folio_clave": "document_number",
        "ID-fecha_expedicion": "issue_date",
        "ID-fecha_vencimiento": "expiry_date",
    },
    "curp": {
        "CURP-curp": "curp",
        "CURP-nombre_completo": "full_name",
        "CURP-fecha_nacimiento": "date_of_birth",
        "CURP-sexo": "sex",
        "CURP-entidad_registro": "entidad_nacimiento",
    },
    "comprobante_domicilio": {
        "DOM-tipo_comprobante": "comprobante_type",
        "DOM-titular": "account_holder_name",
        "DOM-domicilio": "service_address",
        "DOM-fecha_emision": "issue_or_period_date",
        "DOM-cuenta_referencia": "account_reference",
    },
    "acta_constitutiva": {
        "ACTA-denominacion_social": "legal_name",
        "ACTA-tipo_societario": "entity_type",
        "ACTA-fecha_constitucion": "constitution_date",
        "ACTA-rfc": "rfc",
        "ACTA-folio_mercantil": "folio_mercantil",
        "ACTA-notario_numero": "notary.notaria_number",
        "ACTA-notario_nombre": "notary.name",
        "ACTA-entidad_federativa": "notary.entidad_federativa",
        "ACTA-objeto_social": "corporate_purpose",
        "ACTA-capital_fijo": "capital_fijo",
        "ACTA-capital_variable": "capital_variable",
        "ACTA-administracion": "administrators",
        "ACTA-socios_constitucion": "shareholders",
    },
    "poder": {
        "POD-apoderado_nombre": "attorney_name",
        "POD-poderdante": "grantor_legal_name",
        "POD-facultades": "facultades",
        "POD-fecha": "granted_at",
        "POD-instrumento_notarial": "instrumento_notarial",
        "POD-revocacion_consta": "revocacion_consta",
    },
}

for _alias in ("id_representante", "id_controlador"):
    SPEC_FIELDS_BY_KIND[_alias] = SPEC_FIELDS_BY_KIND["official_id"]


def _path_value(payload: dict[str, Any], dotted: str) -> Any:
    current: Any = payload
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def missing_spec_fields(document_kind: str, payload: dict[str, Any] | None) -> list[str]:
    """Return spec campo_ids whose structured value is empty (not 'not found')."""
    mapping = SPEC_FIELDS_BY_KIND.get(document_kind) or {}
    row = payload if isinstance(payload, dict) else {}
    missing = []
    for campo_id, path in mapping.items():
        if not _is_filled(_path_value(row, path)):
            missing.append(campo_id)
    return missing
