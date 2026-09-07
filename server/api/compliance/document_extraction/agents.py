"""Run AgentLoop extractors against a PLD expedient document."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from api.compliance.document_extraction.constants import PLD_EXTRACTION_MODEL_SLUG
from api.compliance.document_extraction.inspect_tool import make_inspect_tool
from api.compliance.document_extraction.schemas import (
    ComprobanteDomicilioExtraction,
    PldExtraction,
    schema_for_kind,
)

logger = logging.getLogger(__name__)

_SHARED_RULES = (
    "Extract only what is visible in the file. Use null when a field is not present. "
    "Never invent RFC, CURP, dates, or ownership percentages. "
    "Call inspect_pld_document with focused questions until you can fill the schema. "
    "Dates as YYYY-MM-DD when possible. "
    "Fill provenances: one row per spec campo_id you extract (see field descriptions), "
    "with pagina_origen, texto_origen snippet, confianza_extraccion 0-1, and "
    "estado_validacion extraido or no_encontrado."
)

INSTRUCTIONS_BY_KIND = {
    "official_id": (
        "You extract Mexican official ID (INE, passport, professional license, or other). "
        "INE does not print RFC — leave RFC-related fields null. "
        + _SHARED_RULES
    ),
    "id_representante": (
        "You extract the official ID of a legal representative. "
        "INE does not print RFC. "
        + _SHARED_RULES
    ),
    "id_controlador": (
        "You extract the official ID of a beneficial owner (beneficiario controlador). "
        "INE does not print RFC. "
        + _SHARED_RULES
    ),
    "curp": (
        "You extract a Mexican CURP certificate / cedula. "
        + _SHARED_RULES
    ),
    "constancia_fiscal": (
        "You extract a SAT Constancia de Situacion Fiscal (or thinner Cedula de Datos Fiscales). "
        "Set document_variant accordingly. "
        + _SHARED_RULES
    ),
    "comprobante_domicilio": (
        "You extract a Mexican proof of address (utility, bank, predial). "
        "Capture issuer, account holder, full address, and issue or billing-period date. "
        "Leave name_matches_client_hint null. "
        + _SHARED_RULES
    ),
    "acta_constitutiva": (
        "You extract a Mexican acta constitutiva / escritura de constitucion. "
        "List every socio or accionista with participation (compute % from partes sociales "
        "only when the numbers are in the deed). "
        "This is ownership at constitution; set ownership_as_of to the constitution date "
        "and ownership_may_be_stale to true. "
        + _SHARED_RULES
    ),
    "poder": (
        "You extract a poder notarial granted by a persona moral. "
        "Identify grantor, apoderado, facultades (administracion, dominio, pleitos y cobranzas), "
        "notary, and escritura number. "
        + _SHARED_RULES
    ),
    "reforma_estatutos": (
        "You extract statutory reforms or asamblea minutes. "
        + _SHARED_RULES
    ),
    "libro_acciones": (
        "You extract a share or partnership-interest registry book. "
        + _SHARED_RULES
    ),
    "declaracion_bc": (
        "You extract a beneficial-owner (beneficiario controlador) declaration. "
        + _SHARED_RULES
    ),
    "contrato": (
        "You extract a contract, service order, or accepted proposal. "
        + _SHARED_RULES
    ),
    "cfdi": (
        "You extract a Mexican CFDI (XML or PDF representation). "
        + _SHARED_RULES
    ),
    "evidencia_materialidad": (
        "You extract materiality evidence of a real operation. "
        + _SHARED_RULES
    ),
    "caratula_bancaria": (
        "You extract a bank account cover or statement. "
        + _SHARED_RULES
    ),
    "comprobante_pago": (
        "You extract a transfer or payment receipt. "
        + _SHARED_RULES
    ),
    "cuestionario_kyc": (
        "You extract a KYC or transactional-profile questionnaire. "
        + _SHARED_RULES
    ),
    "cedula_ft01": (
        "You extract cedula FT-01 (alcance y sujecion). "
        + _SHARED_RULES
    ),
    "ficha_ft02": (
        "You extract ficha FT-02 (tecnica del modelo). "
        + _SHARED_RULES
    ),
    "reporte_ri01": (
        "You extract reporte RI-01 integral. "
        + _SHARED_RULES
    ),
}


def _older_than_three_months(iso: str | None) -> bool | None:
    if not iso:
        return None
    raw = iso.strip()[:10]
    try:
        issued = date.fromisoformat(raw)
    except ValueError:
        return None
    return issued < date.today() - timedelta(days=90)


def _billing_for_document(doc) -> tuple[int | None, object]:
    organization = getattr(doc.expedient, "organization", None)
    org_id = getattr(organization, "id", None)
    owner_id = getattr(organization, "owner_id", None) if organization else None
    user_id = owner_id or getattr(doc, "uploaded_by_id", None)
    return user_id, org_id


def extract_document(doc) -> PldExtraction:
    """Run gpt-5.6-luna AgentLoop and return a validated extraction model."""
    kind = doc.document_kind
    schema = schema_for_kind(kind)
    instructions = INSTRUCTIONS_BY_KIND.get(kind) or _SHARED_RULES
    billing_user_id, organization_id = _billing_for_document(doc)

    from api.ai_layers.agent_loop import AgentLoop

    loop = AgentLoop.create(
        provider="openai",
        tools=[
            make_inspect_tool(
                doc,
                billing_user_id=billing_user_id,
                organization_id=organization_id,
            )
        ],
        instructions=instructions,
        model=PLD_EXTRACTION_MODEL_SLUG,
        output_schema=schema,
        max_iterations=4,
        repair_model=PLD_EXTRACTION_MODEL_SLUG,
    )
    result = loop.run(
        [
            {
                "role": "user",
                "content": (
                    f"Extract structured fields from this {kind} document "
                    f"({doc.original_filename or 'upload'}). "
                    "Inspect the file, then return JSON matching the schema."
                ),
            }
        ]
    )
    usage = result.usage or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    if billing_user_id and (prompt_tokens or completion_tokens):
        from api.consumption.actions import register_llm_interaction

        register_llm_interaction(
            billing_user_id,
            prompt_tokens,
            completion_tokens,
            PLD_EXTRACTION_MODEL_SLUG,
            organization_id=organization_id,
        )

    output = result.output
    if not isinstance(output, schema):
        raise ValueError("Extractor did not return structured output")

    if isinstance(output, ComprobanteDomicilioExtraction):
        output.older_than_three_months = _older_than_three_months(
            output.issue_or_period_date
        )
        output.name_matches_client_hint = None
    return output
