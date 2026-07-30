"""
Tool: list_whatsapp_resources

Lists WhatsApp Business lines assigned to the current agent, with nested
verified contacts (contacts linked to an organization member).
"""

from __future__ import annotations

from django.db.models import Prefetch
from pydantic import BaseModel, Field

from api.authenticate.models import Organization
from api.authenticate.org_membership import user_belongs_to_organization
from api.whatsapp.conversations import resolved_organization_for_ws_number
from api.whatsapp.models import WSContact, WSNumber


class ListWhatsappResourcesParams(BaseModel):
    pass


class WhatsappVerifiedContactSummary(BaseModel):
    ws_contact_id: int
    user_id: int
    number: str
    display_name: str = ""
    user_email: str = ""
    user_display_name: str = ""


class WhatsappResourceSummary(BaseModel):
    sender_id: int
    name: str | None = None
    number: str
    agent_id: int
    agent_slug: str
    agent_name: str
    verified: bool = False
    contacts: list[WhatsappVerifiedContactSummary] = Field(default_factory=list)


class ListWhatsappResourcesResult(BaseModel):
    resources: list[WhatsappResourceSummary] = Field(default_factory=list)


def _contact_user_display_name(contact: WSContact) -> str:
    user = contact.user
    if not user:
        return ""
    profile = getattr(user, "profile", None)
    if profile and (profile.name or "").strip():
        return profile.name.strip()
    return user.username or user.email or ""


def _list_whatsapp_resources_impl(
    *,
    organization_id,
    user_id: int,
    agent_id: int,
) -> ListWhatsappResourcesResult:
    from django.contrib.auth.models import User

    organization = Organization.objects.filter(pk=organization_id).first()
    if not organization:
        raise ValueError("Organization not found")

    actor = User.objects.filter(pk=user_id).first()
    if not actor:
        raise ValueError("Authenticated user not found")
    if not user_belongs_to_organization(actor, organization):
        raise ValueError("User is not a member of this organization")

    try:
        resolved_agent_id = int(agent_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid agent_id: {agent_id}") from exc

    qs = (
        WSNumber.objects.filter(
            organization=organization,
            agent_id=resolved_agent_id,
        )
        .exclude(platform_id__isnull=True)
        .exclude(platform_id="")
        .select_related("agent")
        .prefetch_related(
            Prefetch(
                "contacts",
                queryset=WSContact.objects.filter(user__isnull=False)
                .select_related("user", "user__profile")
                .order_by("number", "id"),
            )
        )
        .order_by("name", "number", "id")
    )

    resources: list[WhatsappResourceSummary] = []
    for ws in qs:
        org = resolved_organization_for_ws_number(ws)
        if not org or org.id != organization.id:
            continue
        agent = ws.agent
        contacts = [
            WhatsappVerifiedContactSummary(
                ws_contact_id=c.id,
                user_id=c.user_id,
                number=c.number,
                display_name=c.display_name or "",
                user_email=(c.user.email or "") if c.user else "",
                user_display_name=_contact_user_display_name(c),
            )
            for c in ws.contacts.all()
            if c.user_id
        ]
        resources.append(
            WhatsappResourceSummary(
                sender_id=ws.id,
                name=ws.name,
                number=ws.number,
                agent_id=agent.id,
                agent_slug=agent.slug,
                agent_name=agent.name,
                verified=bool(ws.verified),
                contacts=contacts,
            )
        )

    return ListWhatsappResourcesResult(resources=resources)


def get_tool(
    organization_id=None,
    user_id: int | None = None,
    agent_id: int | None = None,
    **kwargs,
) -> dict:
    if organization_id is None:
        raise ValueError(
            "list_whatsapp_resources requires organization_id in tool context"
        )
    if user_id is None:
        raise ValueError(
            "list_whatsapp_resources requires user_id in tool context"
        )
    if not isinstance(user_id, int):
        raise ValueError(
            "list_whatsapp_resources requires an authenticated web user"
        )
    if agent_id is None:
        raise ValueError(
            "list_whatsapp_resources requires agent_id in tool context"
        )

    def list_whatsapp_resources() -> ListWhatsappResourcesResult:
        return _list_whatsapp_resources_impl(
            organization_id=organization_id,
            user_id=user_id,
            agent_id=agent_id,
        )

    return {
        "name": "list_whatsapp_resources",
        "description": (
            "List WhatsApp Business lines assigned to you (this agent) that you can "
            "use with send_ws_template_message, each with nested verified contacts "
            "(contacts linked to an organization member). "
            "Returns sender_id, line number/name, linked agent, and contacts with "
            "ws_contact_id, user_id, and phone number. "
            "Only lines with a configured Meta platform_id assigned to this agent "
            "are included. Use a contact's ws_contact_id when sending a template."
        ),
        "parameters": ListWhatsappResourcesParams,
        "function": list_whatsapp_resources,
    }
