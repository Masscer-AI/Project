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
    "COMPLIANCE_ASSISTANT_MODEL_SLUG", "gpt-5.6-terra"
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
        "model_slug": COMPLIANCE_ASSISTANT_MODEL_SLUG,
    }
    update_fields = [
        field for field, value in desired.items() if getattr(agent, field) != value
    ]
    for field in update_fields:
        setattr(agent, field, desired[field])
    if update_fields:
        agent.save(update_fields=update_fields)

    try:
        from api.ai_layers.cache_utils import bump_agent_list_version_for_org_members

        bump_agent_list_version_for_org_members(organization)
    except Exception:
        pass

    return agent, created


COMPLIANCE_ASSISTANT_TOOLS_APPENDIX = """
Herramientas en Masscer para este flujo:
- Chat files: list_attachments, read_attachment (current conversation / expediente only).
- Expediente: list_folio_documents, update_folio_document, update_folio_status.
- Knowledge base (org policies/templates only, not KYB evidence): list_knowledge_base_documents, read_knowledge_base_document, rag_query.
- Generate files: generate_gamma_attachment (set orientation=vertical for a portrait A4 PDF/doc, or horizontal for 16:9 slides; export PDF when the file will be signed), generate_document_file (DOCX), list_document_templates + render_document_template, generate_excel_file.
- Signature: only request_signature sends a PDF to Mifiel. Masscer never requests or stores a .key file or e.firma password.
- Org context: list_organization_members, list_organization_roles, send_email, explore_web.
- Expediente notes: change_conversation_summary, query_organization_tags, create_organization_tag, change_conversation_tags, get_tag_context.
- Follow-up checklists: create_user_assignment, list_user_assignments.
""".strip()

# Stable system prompt for cache hits. Per-request org/invitee data is not interpolated here.
COMPLIANCE_ASSISTANT_INSTRUCTIONS = (
    f"{COMPLIANCE_ASSISTANT_SYSTEM_PROMPT}\n\n{COMPLIANCE_ASSISTANT_TOOLS_APPENDIX}"
)


def build_compliance_runtime_context(
    organization, *, user=None, clock_context: str = ""
) -> str:
    """Per-request invitee/org facts. Append as a developer (or user) message, not in instructions."""
    lines = [f"Organization id: {organization.id}"]
    if user is not None:
        profile = None
        try:
            profile = user.profile
        except Exception:
            profile = None
        invitee = {}
        if profile:
            if (profile.name or "").strip():
                invitee["name"] = profile.name.strip()
            if (profile.bio or "").strip():
                invitee["notes"] = profile.bio.strip()
            if isinstance(profile.intake, dict):
                for key, value in profile.intake.items():
                    if value not in (None, ""):
                        invitee[str(key)] = value
        email = getattr(user, "email", "") or ""
        if email:
            invitee["email"] = email
        if invitee:
            lines.append("Invited user:")
            for key, value in invitee.items():
                lines.append(f"- {key}: {value}")
    if clock_context:
        lines.append(clock_context)
    if user is not None:
        from api.compliance.models import ComplianceFolio
        from api.compliance.folio import folio_runtime_lines

        folio = (
            ComplianceFolio.objects.filter(
                organization=organization, subject_user=user
            )
            .prefetch_related("documents__attachment")
            .first()
        )
        lines.extend(folio_runtime_lines(folio))
    return "\n".join(lines)


def organization_has_compliance_assistant(organization) -> bool:
    if organization is None or not getattr(organization, "id", None):
        return False
    return Agent.objects.filter(
        organization=organization,
        agent_kind=AgentKind.COMPLIANCE_ASSISTANT,
    ).exists()


def get_compliance_agent_for_user(user):
    """Return the compliance assistant the user can access, if any."""
    from api.ai_layers.access import get_user_organizations_for_access
    from api.compliance.access import user_has_organization_compliance_access

    for org in get_user_organizations_for_access(user):
        if not getattr(org, "pld_access_enabled", False):
            continue
        if not user_has_organization_compliance_access(user, org):
            continue
        agent = Agent.objects.filter(
            organization=org,
            agent_kind=AgentKind.COMPLIANCE_ASSISTANT,
        ).first()
        if agent:
            return agent
    return None


def get_or_create_compliance_conversation(user):
    """
    Return the sticky compliance thread for this user and organization.

    One active/inactive conversation per user+org. 404-equivalent when the
    org has no PLD access or no compliance assistant.
    """
    from django.db import transaction

    from api.messaging.models import Conversation
    from api.messaging.schemas import compliance_conversation_metadata

    agent = get_compliance_agent_for_user(user)
    if not agent or not agent.organization_id:
        return None, "not_provisioned"

    org = agent.organization
    with transaction.atomic():
        existing = (
            Conversation.objects.select_for_update()
            .filter(
                user=user,
                organization=org,
                chat_widget__isnull=True,
                ws_number__isnull=True,
                status__in=["active", "inactive"],
                metadata__contains={"surface": "compliance"},
            )
            .order_by("created_at")
            .first()
        )
        if existing:
            from api.compliance.folio import get_or_create_folio

            folio, _ = get_or_create_folio(org, user)
            meta = existing.metadata if isinstance(existing.metadata, dict) else {}
            next_meta = compliance_conversation_metadata(
                agent.id, folio_id=str(folio.id), existing=meta
            )
            if meta != next_meta:
                existing.metadata = next_meta
                existing.save(update_fields=["metadata", "updated_at"])
            return existing, None

        from api.compliance.folio import get_or_create_folio

        folio, _ = get_or_create_folio(org, user)
        conversation = Conversation.objects.create(
            user=user,
            organization=org,
            title=COMPLIANCE_ASSISTANT_NAME,
            metadata=compliance_conversation_metadata(
                agent.id, folio_id=str(folio.id)
            ),
        )
        return conversation, None


def restart_compliance_conversation(user):
    """
    Archive the sticky compliance thread and create a new one.

    Still one active conversation per user+org; the previous thread is archived.
    """
    from django.db import transaction
    from django.utils import timezone

    from api.messaging.models import Conversation
    from api.messaging.schemas import compliance_conversation_metadata

    agent = get_compliance_agent_for_user(user)
    if not agent or not agent.organization_id:
        return None, [], "not_provisioned"

    org = agent.organization
    now = timezone.now()
    with transaction.atomic():
        sticky = list(
            Conversation.objects.select_for_update().filter(
                user=user,
                organization=org,
                chat_widget__isnull=True,
                ws_number__isnull=True,
                status__in=["active", "inactive"],
                metadata__contains={"surface": "compliance"},
            )
        )
        folio_id = None
        for conv in sticky:
            meta = conv.metadata if isinstance(conv.metadata, dict) else {}
            folio_id = folio_id or meta.get("folio_id")
            conv.status = "archived"
            conv.archived_at = now
            conv.save(update_fields=["status", "archived_at", "updated_at"])

        from api.compliance.folio import get_or_create_folio

        folio, _ = get_or_create_folio(org, user)
        conversation = Conversation.objects.create(
            user=user,
            organization=org,
            title=COMPLIANCE_ASSISTANT_NAME,
            metadata=compliance_conversation_metadata(
                agent.id, folio_id=str(folio_id or folio.id)
            ),
        )
        return conversation, sticky, None
