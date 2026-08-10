"""
WhatsApp channel: bridge Meta threads to messaging.Conversation.
"""

from __future__ import annotations

import re

from django.contrib.auth.models import User
from django.db.models import Q

from api.authenticate.models import Organization
from api.messaging.models import Conversation
from api.messaging.schemas import metadata_payload_for_related_agents
from api.whatsapp.models import WSContact


def _digits_only(value: str) -> str:
    return re.sub(r"[^\d]", "", value or "")


def organization_for_user(user: User) -> Organization | None:
    """Resolve org for billing/dashboard (same logic as widget owner)."""
    owned = Organization.objects.filter(owner=user).first()
    if owned:
        return owned
    if hasattr(user, "profile") and user.profile.organization:
        return user.profile.organization
    return None


def organization_ids_accessible_by_user(user: User) -> list:
    """Orgs the user owns or belongs to (via profile)."""
    ids = list(Organization.objects.filter(owner=user).values_list("id", flat=True))
    prof = getattr(user, "profile", None)
    if prof and getattr(prof, "organization_id", None):
        oid = prof.organization_id
        if oid not in ids:
            ids.append(oid)
    return ids


def ws_number_visible_q(user: User) -> Q:
    """WS lines visible to this user (personal owner or org owner/member)."""
    org_ids = organization_ids_accessible_by_user(user)
    q = Q(user=user)
    if org_ids:
        q |= Q(organization_id__in=org_ids)
    return q


def whatsapp_conversation_visible_q(user: User) -> Q:
    """Filter Conversation rows whose linked WSNumber is visible to this user."""
    org_ids = organization_ids_accessible_by_user(user)
    q = Q(ws_number__user=user)
    if org_ids:
        q |= Q(ws_number__organization_id__in=org_ids)
    return q


def resolved_organization_for_ws_number(ws_number) -> Organization | None:
    if getattr(ws_number, "organization_id", None):
        return ws_number.organization
    if ws_number.user_id:
        return organization_for_user(ws_number.user)
    return None


def get_or_create_ws_contact(ws_number, user_phone: str) -> WSContact:
    """Stable contact for (WSNumber, visitor phone); created with user=None."""
    phone = _digits_only(user_phone)
    contact, _ = WSContact.objects.get_or_create(
        ws_number=ws_number,
        number=phone,
        defaults={"display_name": ""},
    )
    return contact


def get_active_whatsapp_conversation(ws_number, user_phone: str) -> Conversation | None:
    """Latest active thread for this line + visitor phone, or None."""
    phone = _digits_only(user_phone)
    return (
        Conversation.objects.filter(
            ws_number=ws_number,
            whatsapp_user_number=phone,
            status="active",
        )
        .order_by("-created_at")
        .first()
    )


def create_whatsapp_conversation(ws_number, user_phone: str) -> Conversation:
    """Create a new active WhatsApp thread (caller must deactivate any prior active row)."""
    phone = _digits_only(user_phone)
    contact = get_or_create_ws_contact(ws_number, phone)
    org = resolved_organization_for_ws_number(ws_number)
    return Conversation.objects.create(
        ws_number=ws_number,
        ws_contact=contact,
        whatsapp_user_number=phone,
        user=None,
        organization=org,
        status="active",
        metadata=metadata_payload_for_related_agents([ws_number.agent_id]),
    )


def get_or_create_whatsapp_conversation(ws_number, user_phone: str) -> Conversation:
    """
    One **active** messaging.Conversation per (WSNumber, visitor WhatsApp phone).

    Like chat-widget threads: ``user`` is always None (anonymous visitor). The
    visitor is identified by ``whatsapp_user_number`` / ``ws_contact``. Organization
    is set for billing and access control. After ``/clear``, older rows are
    inactive and a new active row is created (same WSContact is reused).
    """
    phone = _digits_only(user_phone)
    contact = get_or_create_ws_contact(ws_number, phone)
    active = get_active_whatsapp_conversation(ws_number, phone)
    if active:
        if active.ws_contact_id is None:
            active.ws_contact = contact
            active.save(update_fields=["ws_contact", "updated_at"])
        return active
    return create_whatsapp_conversation(ws_number, phone)


def tool_names_from_capabilities(capabilities: list | None) -> list[str]:
    """
    Same resolution as ChatWidgetAgentTaskView: internal_tool + enabled + registry.
    Required WhatsApp tools are always included.
    """
    from api.ai_layers.tools import list_available_tools, resolve_allowed_tools

    from .capability_tools import (
        WHATSAPP_REQUIRED_CAPABILITY_TOOLS,
        filter_capabilities_for_whatsapp,
    )

    available_tools = set(list_available_tools())
    configured_tools: list[str] = []
    for capability in filter_capabilities_for_whatsapp(capabilities or []):
        if capability.get("type") != "internal_tool":
            continue
        if not capability.get("enabled", False):
            continue
        name = capability.get("name")
        if isinstance(name, str) and name in available_tools:
            configured_tools.append(name)

    for required_tool in WHATSAPP_REQUIRED_CAPABILITY_TOOLS:
        if required_tool in available_tools:
            configured_tools.append(required_tool)

    # WhatsApp senders are phone numbers, never an authenticated Masscer
    # User — drop any tool that requires one, same as the chat widget.
    return resolve_allowed_tools(configured_tools, user=None)
