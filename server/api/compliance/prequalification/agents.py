"""LLM review of identification completeness and consistency (not list screening)."""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, ConfigDict, Field

from api.compliance.document_extraction.constants import PLD_EXTRACTION_MODEL_SLUG
from api.compliance.pld_document_slots import required_slots_extraction_ready
from api.compliance.prequalification.deterministic import controller_names
from api.compliance.prequalification.pack import build_prequalification_packet
from api.compliance.prequalification.schemas import PrequalificationResult
from api.compliance.prequalification.sources import RULESET_VERSION

logger = logging.getLogger(__name__)

INSTRUCTIONS = """
Eres el agente de precalificacion de identificacion PLD de Masscer.
Tu unico trabajo es decidir si el expediente unico de identificacion esta completo
y consistente ANTES del cruce con listas (PEP, listas negativas) y ANTES de la
matriz de riesgo / semaforo.

Reglas:
- Evalua SOLO contra el objeto `rules` del paquete (Anexos 3/4 RCG, LFPIORPI).
- No inventes requisitos que no esten en `rules`.
- No consultes listas, no asignes semaforo, no declares PEP.
- Trata abreviaciones societarias (SA de CV vs sociedad anonima de capital variable)
  y campos opcionales del acta (RFC de la sociedad, folio mercantil, objeto social)
  con holgura. No pidas aclaracion por esas diferencias menores.
- Si falta un dato o hay inconsistencia que el invitado puede aclarar, llena
  `invitee_requests` (maximo 5). Cada prompt en espanol, breve, sin mencionar listas,
  scores ni investigaciones. answer_type: text, document o either.
- El objeto `declared` es el formulario vigente. No copies preguntas anteriores.
- No menciones valores de colonia, CURP u otros campos que ya no esten en `declared`.
- El acta constitutiva es un retrato a la fecha de constitucion. No emitas hallazgo
  solo porque la fecha es antigua o el acta dice que la participacion es de entonces.
  Solo senala socios o controladores si `declared` contradice al acta.
- Nunca inventes RFC, CURP, fechas ni porcentajes.
- summary en espanol, breve, para la contraparte (sin jerga interna de scoring).
- source_ids solo de: lfpiorpi, reglamento, rcg, uif-portal.
""".strip()


class ClarificationTextCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")

    request_id: str
    satisfies: bool


class ClarificationSettleResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    checks: list[ClarificationTextCheck] = Field(default_factory=list)


_SETTLE_INSTRUCTIONS = """
You settle identification clarifications for one expediente.
You see every answered clarification and any text answer still waiting.
Call fill_form_variable only when an answer clearly corrects a form field.
Call each field path at most once.
If two answers mention the same field, write the value that answers that question, once.
Do not invent RFC, CURP, dates, percentages, or addresses.
For each waiting text answer, set satisfies true only if that text answers its prompt.
Return checks only for waiting text answers.
""".strip()


def _clarification_rows(expedient) -> tuple[list[dict], list]:
    from api.compliance.clarifications import answers_packet, text_reviews
    from api.compliance.models import PLDClarificationRequest

    reviews = text_reviews(expedient)
    answered = {row["id"]: row for row in answers_packet(expedient)}
    docs = {doc.slot_key: doc for doc in expedient.documents.all()}
    rows = []
    waiting = []
    for item in expedient.clarification_requests.exclude(
        status=PLDClarificationRequest.Status.CANCELLED
    ):
        if item.status == PLDClarificationRequest.Status.ANSWERED:
            packet = answered.get(str(item.id))
            if packet:
                rows.append({**packet, "waiting": False})
            continue
        if reviews.get(str(item.id)) != "reviewing" or not (item.text_answer or "").strip():
            continue
        doc = docs.get(item.slot_key)
        payload = doc.extracted_payload if doc and isinstance(doc.extracted_payload, dict) else {}
        rows.append(
            {
                "id": str(item.id),
                "prompt": item.prompt,
                "text_answer": item.text_answer,
                "document_extraction": payload or None,
                "waiting": True,
            }
        )
        waiting.append(item)
    return rows, waiting


def settle_clarification_answers(expedient) -> None:
    from api.compliance.clarifications import mark_answered, set_text_review, text_reviews
    from api.compliance.document_extraction.fill_form_tool import (
        form_field_snapshot,
        make_fill_form_variable_tool,
    )

    from api.compliance.models import PLDClarificationRequest

    reviews = text_reviews(expedient)
    for item in expedient.clarification_requests.filter(
        status=PLDClarificationRequest.Status.ANSWERED
    ):
        if reviews.get(str(item.id)) == "reviewing":
            set_text_review(expedient, item.id, None)
    rows, waiting = _clarification_rows(expedient)
    if not rows:
        return
    entity = expedient.entity
    filled, empty = form_field_snapshot(getattr(entity, "metadata", None))
    billing_user_id, organization_id = _billing(entity)
    from api.ai_layers.agent_loop import AgentLoop

    loop = AgentLoop.create(
        provider="openai",
        tools=[make_fill_form_variable_tool(entity, once=True)],
        instructions=_SETTLE_INSTRUCTIONS,
        model=PLD_EXTRACTION_MODEL_SLUG,
        output_schema=ClarificationSettleResult,
        max_iterations=8,
        repair_model=PLD_EXTRACTION_MODEL_SLUG,
    )
    result = loop.run(
        [
            {
                "role": "user",
                "content": (
                    "Settle these clarifications. Write each form field at most once.\n"
                    f"Filled: {json.dumps(filled, ensure_ascii=False)}\n"
                    f"Empty: {json.dumps(empty)}\n"
                    f"Clarifications:\n{json.dumps(rows, ensure_ascii=False, default=str)}"
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
    checks = output.checks if isinstance(output, ClarificationSettleResult) else []
    accepted = {check.request_id for check in checks if check.satisfies}
    for item in waiting:
        if str(item.id) in accepted:
            mark_answered(item)
            set_text_review(expedient, item.id, None)
        else:
            set_text_review(expedient, item.id, "rejected")


def _billing(entity) -> tuple[int | None, object]:
    org = getattr(entity, "organization", None)
    owner_id = getattr(org, "owner_id", None) if org else None
    return owner_id, getattr(org, "id", None)


def run_prequalification(entity) -> PrequalificationResult:
    ready, _reason = required_slots_extraction_ready(entity)
    if not ready:
        return PrequalificationResult(
            ruleset_version=RULESET_VERSION,
            verdict="blocked",
            summary=(
                "Aun no se puede precalificar: faltan documentos obligatorios "
                "o la extraccion no ha terminado."
            ),
            findings=[],
            controllers=controller_names(entity),
        )

    packet = build_prequalification_packet(entity)
    billing_user_id, organization_id = _billing(entity)

    from api.ai_layers.agent_loop import AgentLoop

    loop = AgentLoop.create(
        provider="openai",
        tools=[],
        instructions=INSTRUCTIONS,
        model=PLD_EXTRACTION_MODEL_SLUG,
        output_schema=PrequalificationResult,
        max_iterations=2,
        repair_model=PLD_EXTRACTION_MODEL_SLUG,
    )
    result = loop.run(
        [
            {
                "role": "user",
                "content": (
                    "Precalifica este expediente de identificacion. "
                    "Devuelve JSON del schema. Paquete:\n"
                    + packet
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
    if not isinstance(output, PrequalificationResult):
        raise ValueError("Prequalification did not return structured output")

    findings = list(output.findings or [])
    verdict = output.verdict
    from api.compliance.clarifications import merge_request_specs

    requests = merge_request_specs(list(output.invitee_requests or []))
    if requests and verdict == "ready_for_list_screening":
        verdict = "needs_review"
    controllers = output.controllers or controller_names(entity)
    summary = output.summary.strip() if output.summary else ""
    if not summary:
        if requests:
            summary = "Necesitamos que confirmes algunos datos o documentos para continuar."
        elif verdict == "blocked":
            summary = "Faltan datos o documentos obligatorios, o hay inconsistencias que impiden el cruce de listas."
        elif verdict == "needs_review":
            summary = "La identificacion esta integrada, con observaciones para revision humana."
        else:
            summary = "La identificacion esta completa y consistente para pasar al cruce de listas."
    return PrequalificationResult(
        ruleset_version=RULESET_VERSION,
        verdict=verdict,
        summary=summary,
        findings=findings,
        controllers=controllers,
        human_notes=output.human_notes,
        invitee_requests=requests,
    )
