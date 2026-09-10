"""List screening after identification is complete."""

from __future__ import annotations

import json
import logging
import re

from api.compliance.clarifications import answers_packet
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
- Si hace falta aclarar identidad con el invitado, llena invitee_requests
  (espanol, sin mencionar listas, scores ni investigaciones).
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


def build_screening_packet(entity) -> str:
    exp = entity.expedients.order_by("created_at").first()
    packet = {
        "person_type": entity.person_type,
        "declared": entity.metadata if isinstance(entity.metadata, dict) else {},
        "rfcs": _rfcs_from_entity(entity),
        "rfc_hits": _deterministic_rfc_hits(entity),
        "prior_invitee_answers": answers_packet(exp) if exp else [],
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
    if output.invitee_requests and output.verdict == "clear":
        output.verdict = "needs_invitee_input"
    if not output.summary.strip():
        if output.invitee_requests:
            output.summary = "Necesitamos que confirmes algunos datos para continuar."
        elif output.verdict == "clear":
            output.summary = "Tu expediente sigue en revision interna."
        else:
            output.summary = "Tu expediente requiere revision adicional."
    return output
