"""Run AgentLoop extractors against a PLD expedient document."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from api.compliance.document_extraction.constants import PLD_EXTRACTION_MODEL_SLUG
from api.compliance.document_extraction.hydrate import hydrate_extraction
from api.compliance.document_extraction.inspect_tool import extraction_user_content
from api.compliance.document_extraction.schemas import (
    ComprobanteDomicilioExtraction,
    PldExtraction,
    schema_for_kind,
)

logger = logging.getLogger(__name__)

_SHARED_RULES = (
    "The document is attached to this message. "
    "Fill every property on this document's JSON schema first; those names are the "
    "source of truth. Do not invent extra top-level keys such as addresses or dates. "
    "If a value is visible, extract it even if the file is labeled sample, draft, or ficticio. "
    "Use null only when the field is not visible. Never invent RFC, CURP, dates, or "
    "ownership percentages. Dates as YYYY-MM-DD when possible. "
    "Then call fill_form_variable for form fields the document shows: fill empties, "
    "and replace a filled value when it disagrees with the document. "
    "Set summary to what you extracted and which form fields you wrote or corrected. "
    "Provenances are citations only: campo_id must be the schema property name or the "
    "code in that field's description (e.g. issue_or_period_date or DOM-fecha_emision), "
    "valor_extraido must be the same value you put in the schema field, pagina_origen "
    "as a string (e.g. \"1\"), plus a short texto_origen snippet."
)

_INE_ID_RULES = (
    "INE does not print RFC. "
    "On INE, the identification number is on the reverse (parte de atras): the digits "
    "immediately after IDMEX on the MRZ. Example: IDMEX1726181815 -> 1726181815. "
    "Put those digits in document_number and cic. Never put clave de elector in "
    "document_number. Put clave de elector in citizen_identifier. Put the digits after "
    "<< on that same MRZ line in ocr_line. Copy the three MRZ lines into mrz. "
    "If the reverse is not in the file, leave document_number and cic null. "
    "Set document_subtype, full_name, date_of_birth, sex, validity_year or "
    "expiry_date, and address_text. "
    "If a fact is present in provenances, place it in its matching schema property too. "
)

INSTRUCTIONS_BY_KIND = {
    "official_id": (
        "You extract Mexican official ID (INE, passport, professional license, or other). "
        "Copy CURP exactly as printed, character by character. "
        + _INE_ID_RULES
        + _SHARED_RULES
    ),
    "id_representante": (
        "You extract the official ID of a legal representative. "
        "Do not extract CURP. Leave curp null. CURP comes only from the CURP document. "
        + _INE_ID_RULES
        + _SHARED_RULES
    ),
    "id_controlador": (
        "You extract the official ID of a beneficial owner (beneficiario controlador). "
        + _INE_ID_RULES
        + _SHARED_RULES
    ),
    "curp": (
        "You extract a Mexican CURP certificate / cedula. "
        "Set curp, full_name, date_of_birth, sex, and entidad_nacimiento. "
        "If a fact is present in provenances, place it in its matching schema property too. "
        + _SHARED_RULES
    ),
    "constancia_fiscal": (
        "You extract a SAT Constancia de Situacion Fiscal (or thinner Cedula de Datos Fiscales). "
        "Set document_variant accordingly. "
        + _SHARED_RULES
    ),
    "comprobante_domicilio": (
        "You extract a Mexican proof of address (utility bill, CFDI, bank, predial). "
        "Set issuer to the company that issued the bill, not the customer. "
        "Set account_holder_name to the billed customer name. "
        "Set service_address to an object and service_address.raw_text to the full address. "
        "Set issue_or_period_date to the billing period or certification date, "
        "not the payment deadline. Set comprobante_type (telefono, luz, agua, "
        "predial, or other). Use only DOM-titular, DOM-domicilio, DOM-fecha_emision, "
        "DOM-tipo_comprobante, and DOM-cuenta_referencia as campo_id values for these fields. "
        "Never use legal_name, account_holder, addresses, dates, or dates.* as campo_id. "
        "If a fact is present in provenances, place it in its matching schema property too. "
        "Leave name_matches_client_hint and older_than_three_months null. "
        + _SHARED_RULES
    ),
    "acta_constitutiva": (
        "You extract a Mexican acta constitutiva / escritura de constitucion. "
        "List every socio or accionista with participation (compute % from partes sociales "
        "only when the numbers are in the deed). "
        "Set ownership_as_of to the constitution date. Leave ownership_may_be_stale null. "
        "Write form fields from the deed: legal_name, constitution_date, nationality "
        "(ISO-2 from the registered domicile country), economic_activity from objeto social, "
        "address.* from domicilio social, and controllers from socios. "
        + _SHARED_RULES
    ),
    "poder": (
        "You extract a poder notarial granted by a persona moral. "
        "Identify grantor, apoderado, facultades (administracion, dominio, pleitos y cobranzas), "
        "notary, and escritura number. "
        + _SHARED_RULES
    ),
    "acta_nacimiento": (
        "You extract a Mexican birth certificate (acta de nacimiento). "
        + _SHARED_RULES
    ),
    "organigrama": (
        "You extract an institutional organization chart: people and roles. "
        + _SHARED_RULES
    ),
    "curp_representante": (
        "You extract the CURP certificate of the legal representative. "
        "Set curp, full_name, date_of_birth, sex, and entidad_nacimiento. "
        "If a fact is present in provenances, place it in its matching schema property too. "
        + _SHARED_RULES
    ),
    "curp_socios": (
        "You extract CURP certificates of shareholders or partners. List each person. "
        + _SHARED_RULES
    ),
    "matriz_accionaria": (
        "You extract a shareholder / ownership matrix. "
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
    "clarification": (
        "You extract an extra supporting document the client uploaded to answer "
        "a clarification question. Summarize visible identity and tax identifiers. "
        + _SHARED_RULES
    ),
}


def _extraction_output_summary(output) -> dict:
    payload = output.model_dump(mode="json")
    provenances = payload.pop("provenances", [])
    return {
        "populated_fields": [
            key for key, value in payload.items() if value not in (None, "", [], {})
        ],
        "empty_fields": [
            key for key, value in payload.items() if value in (None, "", [], {})
        ],
        "provenance_campo_ids": [
            row.get("campo_id") for row in provenances if isinstance(row, dict)
        ],
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
    logger.info(
        "PLD extraction input doc=%s kind=%s schema=%s fields=%s",
        getattr(doc, "pk", None),
        kind,
        schema.__name__,
        list(schema.model_fields),
    )

    from api.ai_layers.agent_loop import AgentLoop
    from api.compliance.document_extraction.fill_form_tool import (
        apply_extraction_to_form,
        form_fill_prompt,
        make_fill_form_variable_tool,
    )

    entity = getattr(getattr(doc, "expedient", None), "entity", None)
    tools = [make_fill_form_variable_tool(entity)] if entity is not None else []
    loop = AgentLoop.create(
        provider="openai",
        tools=tools,
        instructions=instructions,
        model=PLD_EXTRACTION_MODEL_SLUG,
        output_schema=schema,
        max_iterations=8,
        repair_model=PLD_EXTRACTION_MODEL_SLUG,
    )
    prompt = (
        f"Extract structured fields from this {kind} document "
        f"({doc.original_filename or 'upload'}). "
        "Read the attached file and return JSON matching the schema. "
        "Put values on schema properties, not only in provenances."
    )
    if entity is not None:
        prompt = f"{prompt}\n\n{form_fill_prompt(entity)}"
    result = loop.run(
        [
            {
                "role": "user",
                "content": extraction_user_content(doc, prompt),
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
        preview = output if isinstance(output, str) else repr(output)
        logger.warning(
            "PLD extraction final response was not %s (kind=%s doc=%s):\n%s",
            schema.__name__,
            kind,
            getattr(doc, "pk", None),
            preview,
        )
        raise ValueError("Extractor did not return structured output")

    logger.info(
        "PLD extraction before hydration doc=%s summary=%s",
        getattr(doc, "pk", None),
        _extraction_output_summary(output),
    )
    output = hydrate_extraction(output, kind)
    logger.info(
        "PLD extraction after hydration doc=%s summary=%s",
        getattr(doc, "pk", None),
        _extraction_output_summary(output),
    )

    if isinstance(output, ComprobanteDomicilioExtraction):
        output.older_than_three_months = _older_than_three_months(
            output.issue_or_period_date
        )
        output.name_matches_client_hint = None
    if entity is not None:
        apply_extraction_to_form(entity, kind, output.model_dump(mode="json"))
    return output
