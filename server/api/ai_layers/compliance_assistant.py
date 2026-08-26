"""
Compliance assistant provisioning and prompt constants.

Enabled only via Django admin (idempotent get_or_create). Not created on org
signup. Behavior (prompt, tools) is defined here in code, not via user-editable
DB fields.
"""

from __future__ import annotations

import os
from pathlib import Path

from api.ai_layers.models import Agent, AgentKind

COMPLIANCE_ASSISTANT_NAME = "MASSCER CUMPLIMIENTO 115"
COMPLIANCE_ASSISTANT_SLUG_PREFIX = "masscer-compliance"

COMPLIANCE_ASSISTANT_MODEL_SLUG: str = os.environ.get(
    "COMPLIANCE_ASSISTANT_MODEL_SLUG", "gpt-5.5-mini"
)

# Matches the source agent row; the operational brief lives in the system prompt file.
COMPLIANCE_ASSISTANT_ACT_AS = "You are a helpful assistant."

COMPLIANCE_ASSISTANT_SALUTE = (
    "Hola. Bienvenido(a) al proceso de registro y validacion documental de Masscer. "
    "Te acompano paso a paso para integrar el expediente."
)

COMPLIANCE_ASSISTANT_CONVERSATION_TITLE_PROMPT = """
Given the first messages in a Masscer compliance/e-sign chat, generate a short conversation title.
The title must start with one emoji, then plain text (no quotes). Max 50 characters.
Focus on what the user asked about (e.g. signing a ficha, requesting e.firma).
Examples: ✍️ Firma de acuse documental, 📄 Enviar PDF a e.firma
Return ONLY the title (emoji + text).
""".strip()

_SYSTEM_PROMPT_PATH = Path(__file__).with_name("compliance_assistant_system_prompt.txt")
COMPLIANCE_ASSISTANT_SYSTEM_PROMPT = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


def compliance_assistant_slug_for_org(org_id) -> str:
    org_str = str(org_id).replace("-", "")[:8]
    return f"{COMPLIANCE_ASSISTANT_SLUG_PREFIX}-{org_str}"


def provision_compliance_assistant(organization) -> tuple[Agent, bool]:
    """
    Idempotently create the compliance assistant for an organization.

    Only called from Django admin (not org-create signals). Returns (agent, created).
    """
    slug = compliance_assistant_slug_for_org(organization.id)
    agent, created = Agent.objects.get_or_create(
        organization=organization,
        agent_kind=AgentKind.COMPLIANCE_ASSISTANT,
        defaults={
            "name": COMPLIANCE_ASSISTANT_NAME,
            "slug": slug,
            "salute": COMPLIANCE_ASSISTANT_SALUTE,
            "act_as": COMPLIANCE_ASSISTANT_ACT_AS,
            "conversation_title_prompt": COMPLIANCE_ASSISTANT_CONVERSATION_TITLE_PROMPT,
            "system_prompt": COMPLIANCE_ASSISTANT_SYSTEM_PROMPT,
            "user": None,
            "model_provider": "openai",
            "model_slug": COMPLIANCE_ASSISTANT_MODEL_SLUG,
        },
    )
    # Re-running the admin action must refresh code-managed fields on existing rows.
    desired = {
        "slug": slug,
        "name": COMPLIANCE_ASSISTANT_NAME,
        "act_as": COMPLIANCE_ASSISTANT_ACT_AS,
        "salute": COMPLIANCE_ASSISTANT_SALUTE,
        "conversation_title_prompt": COMPLIANCE_ASSISTANT_CONVERSATION_TITLE_PROMPT,
        "system_prompt": COMPLIANCE_ASSISTANT_SYSTEM_PROMPT,
    }
    if not agent.llm_id:
        desired["model_slug"] = COMPLIANCE_ASSISTANT_MODEL_SLUG
    update_fields = [
        field for field, value in desired.items() if getattr(agent, field) != value
    ]
    for field in update_fields:
        setattr(agent, field, desired[field])
    if update_fields:
        agent.save(update_fields=update_fields)

    if created or update_fields:
        try:
            from api.ai_layers.cache_utils import bump_agent_list_version_for_org_members

            bump_agent_list_version_for_org_members(organization)
        except Exception:
            pass

    return agent, created


def build_compliance_assistant_instructions(organization, *, clock_context: str = "") -> str:
    """Build runtime instructions from code constants + live org context."""
    from api.authenticate.models import UserProfile

    member_count = UserProfile.objects.filter(organization=organization).count()
    owner_email = ""
    if organization.owner_id:
        owner_email = getattr(organization.owner, "email", "") or ""

    plan_slug = ""
    sub = organization.subscriptions.select_related("plan").order_by("-created_at").first()
    if sub and sub.plan_id:
        plan_slug = sub.plan.slug or ""

    context_lines = [
        f"Organization name: {organization.name}",
        f"Organization id: {organization.id}",
        f"Member count (profiles linked to org): {member_count}",
    ]
    if owner_email:
        context_lines.append(f"Owner email: {owner_email}")
    if plan_slug:
        context_lines.append(f"Subscription plan: {plan_slug}")
    if organization.description:
        context_lines.append(f"Description: {organization.description}")

    context = "\n".join(context_lines)
    formatted = COMPLIANCE_ASSISTANT_SYSTEM_PROMPT.replace(
        "{{act_as}}", COMPLIANCE_ASSISTANT_ACT_AS
    ).replace("{{context}}", context)
    formatted += (
        "\n\nHerramientas de firma en Masscer: list_attachments, read_attachment, "
        "request_signature. Solo request_signature envia un PDF a Mifiel. "
        "Masscer nunca solicita ni almacena archivo .key ni contrasena de e.firma."
    )
    if clock_context:
        formatted += f"\n{clock_context}"
    return formatted
