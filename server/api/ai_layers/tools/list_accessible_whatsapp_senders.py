"""
Tool: list_accessible_whatsapp_senders

Lists WhatsApp Business senders (WSNumber) the authenticated user may use
for organization-scoped template messaging.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.ai_layers.access import accessible_agents_qs
from api.authenticate.models import Organization
from api.authenticate.org_membership import user_belongs_to_organization
from api.whatsapp.conversations import resolved_organization_for_ws_number
from api.whatsapp.models import WSNumber


class ListAccessibleWhatsappSendersParams(BaseModel):
    pass


class WhatsappSenderSummary(BaseModel):
    sender_id: int
    name: str | None = None
    number: str
    agent_id: int
    agent_slug: str
    agent_name: str
    verified: bool = False


class ListAccessibleWhatsappSendersResult(BaseModel):
    senders: list[WhatsappSenderSummary] = Field(default_factory=list)


def _list_accessible_whatsapp_senders_impl(
    *,
    organization_id,
    user_id: int,
) -> ListAccessibleWhatsappSendersResult:
    from django.contrib.auth.models import User

    organization = Organization.objects.filter(pk=organization_id).first()
    if not organization:
        raise ValueError("Organization not found")

    actor = User.objects.filter(pk=user_id).first()
    if not actor:
        raise ValueError("Authenticated user not found")
    if not user_belongs_to_organization(actor, organization):
        raise ValueError("User is not a member of this organization")

    accessible_agent_ids = set(
        accessible_agents_qs(actor).values_list("id", flat=True)
    )

    senders: list[WhatsappSenderSummary] = []
    qs = (
        WSNumber.objects.filter(organization=organization)
        .exclude(platform_id__isnull=True)
        .exclude(platform_id="")
        .select_related("agent")
        .order_by("name", "number", "id")
    )
    for ws in qs:
        # Defensive: also accept lines whose org is resolved via owner.
        org = resolved_organization_for_ws_number(ws)
        if not org or org.id != organization.id:
            continue
        if ws.agent_id not in accessible_agent_ids:
            continue
        agent = ws.agent
        senders.append(
            WhatsappSenderSummary(
                sender_id=ws.id,
                name=ws.name,
                number=ws.number,
                agent_id=agent.id,
                agent_slug=agent.slug,
                agent_name=agent.name,
                verified=bool(ws.verified),
            )
        )

    return ListAccessibleWhatsappSendersResult(senders=senders)


def get_tool(
    organization_id=None,
    user_id: int | None = None,
    **kwargs,
) -> dict:
    if organization_id is None:
        raise ValueError(
            "list_accessible_whatsapp_senders requires organization_id in tool context"
        )
    if user_id is None:
        raise ValueError(
            "list_accessible_whatsapp_senders requires user_id in tool context"
        )
    if not isinstance(user_id, int):
        raise ValueError(
            "list_accessible_whatsapp_senders requires an authenticated web user"
        )

    def list_accessible_whatsapp_senders() -> ListAccessibleWhatsappSendersResult:
        return _list_accessible_whatsapp_senders_impl(
            organization_id=organization_id,
            user_id=user_id,
        )

    return {
        "name": "list_accessible_whatsapp_senders",
        "description": (
            "List WhatsApp Business senders (phone lines) in the current organization "
            "that you can use with send_ws_template_message. "
            "Returns sender_id, display number/name, and the linked agent. "
            "Only lines with a configured Meta platform_id and an agent you can access "
            "are included."
        ),
        "parameters": ListAccessibleWhatsappSendersParams,
        "function": list_accessible_whatsapp_senders,
    }
