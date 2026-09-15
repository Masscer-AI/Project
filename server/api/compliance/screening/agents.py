"""List screening after identification is complete."""

from __future__ import annotations

import json
import logging
import re

from api.compliance.clarifications import answers_packet
from api.compliance.models import PLDExpedientDocument
from api.compliance.prequalification.pack import _compact_payload
from api.compliance.document_extraction.constants import PLD_EXTRACTION_MODEL_SLUG
from api.compliance.screening.schemas import ScreeningResult
from api.compliance.screening.search_tool import (
    RFC_SEARCH_LISTS,
    search_watchlists_impl,
)

logger = logging.getLogger(__name__)

INSTRUCTIONS = """
Eres el agente de cruce de listas PLD de Masscer.
Consulta solo mediante search_watchlists. No inventes coincidencias.
Reglas:
- Busca RFC de la persona moral, titular, representante y cada controlador.
- Busca nombres (varias llamadas si hay alias o orden distinto). AND por llamada.
- Distingue fuerza: exact (mismo RFC o nombre+fecha), strong, weak, none.
- SAT situacion desvirtuado o sentencia favorable no es escalate por si sola.
- ONU o SAT definitivo/presunto/firmes con coincidencia exacta => escalate.
- La identificacion ya esta precalificada. No pidas confirmar ni volver a subir
  INE, CURP u otro documento que ya este en `documents`.
- invitee_requests solo si un hit de lista es ambiguo y falta un dato que NO
  esta en `declared` ni en `documents`.
- summary para la contraparte: neutro (faltan datos o expediente en revision).
- human_notes interno para cumplimiento.
- Nunca afirmes que se consulto una lista si no llamaste la herramienta.
""".strip()


def _rfcs_from_entity(entity) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(value):
        text = re.sub(r"\s+", "", str(value or "")).upper()
        if len(text) in {12, 13} and text not in seen:
            seen.add(text)
            found.append(text)

    meta = entity.metadata if isinstance(entity.metadata, dict) else {}
    add(meta.get("rfc"))
    exp = entity.expedients.order_by("created_at").first()
    if exp:
        for doc in exp.documents.all():
            payload = doc.extracted_payload if isinstance(doc.extracted_payload, dict) else {}
            add(payload.get("rfc"))
    return found


def _deterministic_rfc_hits(entity) -> list[dict]:
    hits = []
    for rfc in _rfcs_from_entity(entity):
        result = search_watchlists_impl([rfc], list_slug=None)
        for hit in result.hits:
            hits.append(hit.model_dump(mode="json"))
    return hits[:40]


_ID_REASK = re.compile(
    r"ine|identificaci|clave de elector|credencial|constancia documental",
    re.I,
)


def _document_rows(entity) -> list[dict]:
    exp = entity.expedients.order_by("created_at").first()
    docs = []
    if not exp:
        return docs
    for doc in exp.documents.all():
        payload = doc.extracted_payload if isinstance(doc.extracted_payload, dict) else {}
        docs.append(
            {
                "slot_key": doc.slot_key,
                "document_kind": doc.document_kind,
                "original_filename": doc.original_filename,
                "extraction_status": doc.extraction_status,
                "extracted": _compact_payload(payload),
            }
        )
    return docs


def _has_extracted_official_id(entity) -> bool:
    for row in _document_rows(entity):
        if row["document_kind"] not in {
            "official_id",
            "id_representante",
            "id_controlador",
        }:
            continue
        if row["extraction_status"] != PLDExpedientDocument.ExtractionStatus.SUCCEEDED:
            continue
        extracted = row.get("extracted") or {}
        if extracted.get("document_number") or extracted.get("full_name"):
            return True
    return False


def _filter_screening_requests(entity, specs: list) -> list:
    if not _has_extracted_official_id(entity):
        return specs
    return [spec for spec in specs if not _ID_REASK.search(spec.prompt or "")]


def build_screening_packet(entity) -> str:
    exp = entity.expedients.order_by("created_at").first()
    packet = {
        "person_type": entity.person_type,
        "declared": entity.metadata if isinstance(entity.metadata, dict) else {},
        "documents": _document_rows(entity),
        "rfcs": _rfcs_from_entity(entity),
        "rfc_hits": _deterministic_rfc_hits(entity),
        "prior_invitee_answers": [
            {
                **row,
                "document_extraction": (
                    _compact_payload(row["document_extraction"])
                    if isinstance(row.get("document_extraction"), dict)
                    else row.get("document_extraction")
                ),
            }
            for row in (answers_packet(exp) if exp else [])
        ],
        "lists_available": list(RFC_SEARCH_LISTS) + ["onu_csnu"],
    }
    return json.dumps(packet, ensure_ascii=False, default=str)


def run_screening(entity) -> ScreeningResult:
    from api.ai_layers.agent_loop import AgentLoop
    from api.compliance.screening.search_tool import make_search_watchlists_tool

    org = getattr(entity, "organization", None)
    billing_user_id = getattr(org, "owner_id", None) if org else None
    organization_id = getattr(org, "id", None) if org else None
    loop = AgentLoop.create(
        provider="openai",
        tools=[make_search_watchlists_tool()],
        instructions=INSTRUCTIONS,
        model=PLD_EXTRACTION_MODEL_SLUG,
        output_schema=ScreeningResult,
        max_iterations=8,
        repair_model=PLD_EXTRACTION_MODEL_SLUG,
    )
    result = loop.run(
        [
            {
                "role": "user",
                "content": (
                    "Cruza este expediente con las listas. "
                    "Usa search_watchlists. Devuelve JSON del schema. Paquete:\n"
                    + build_screening_packet(entity)
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
    if not isinstance(output, ScreeningResult):
        raise ValueError("Screening did not return structured output")
    by_ref = {
        str(row.get("reference_number") or ""): row
        for row in _deterministic_rfc_hits(entity)
    }
    enriched = []
    for hit in output.hits:
        row = by_ref.get(hit.reference_number) or {}
        situation = hit.situation or str(row.get("situation") or "")
        enriched.append(hit.model_copy(update={"situation": situation}))
    output.hits = enriched
    output.invitee_requests = _filter_screening_requests(
        entity, list(output.invitee_requests or [])
    )
    if output.invitee_requests and output.verdict == "clear":
        output.verdict = "needs_invitee_input"
    if not output.invitee_requests and output.verdict == "needs_invitee_input":
        if any(hit.strength in {"exact", "strong"} for hit in output.hits):
            output.verdict = "human_review"
        else:
            output.verdict = "clear"
    if not output.summary.strip():
        if output.invitee_requests:
            output.summary = "Necesitamos que confirmes algunos datos para continuar."
        elif output.verdict == "clear":
            output.summary = "Tu expediente sigue en revision interna."
        else:
            output.summary = "Tu expediente requiere revision adicional."
    return output
