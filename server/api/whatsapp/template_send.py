"""
Scoped WhatsApp template delivery for organization-member tooling.

Security invariants:
- Template id must be in the local allowlist.
- Sender must be a WSNumber in the actor's organization with an accessible agent.
- Target must be a WSContact on that sender with user linked to an active org member.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from django.contrib.auth.models import User
from pydantic import BaseModel, ConfigDict, Field

from api.ai_layers.access import accessible_agents_qs
from api.authenticate.models import Organization
from api.authenticate.org_membership import (
    iter_organization_member_users,
    user_belongs_to_organization,
)
from api.messaging.models import Conversation, Message
from api.whatsapp.actions import send_template_message
from api.whatsapp.conversations import (
    create_whatsapp_conversation,
    get_active_whatsapp_conversation,
    resolved_organization_for_ws_number,
)
from api.whatsapp.models import WSContact, WSNumber
from api.whatsapp.template_registry import (
    WhatsAppTemplateDefinition,
    get_template,
)

logger = logging.getLogger(__name__)

_DIGITS_RE = re.compile(r"[^\d]")


class TemplateVariables(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: list[str] = Field(
        default_factory=list,
        description="Values for body {{1}}, {{2}}, ... in positional order.",
    )
    buttons: list[str] | None = Field(
        default=None,
        description=(
            "Manual button variables in positional order. Omit or use null when "
            "URL buttons are filled automatically from the source conversation."
        ),
    )


class SendWsTemplateResult(BaseModel):
    sent: bool
    message: str
    wamid: str | None = None
    delivery_conversation_id: str | None = None
    template_id: str | None = None
    target_phone: str | None = None
    ws_contact_id: int | None = None


def _digits_only(value: str) -> str:
    return _DIGITS_RE.sub("", value or "")


def _resolve_sender(
    *,
    sender_id: int | str,
    organization: Organization,
    actor: User,
) -> WSNumber:
    try:
        pk = int(sender_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid sender_id: {sender_id}") from exc

    ws_number = (
        WSNumber.objects.filter(pk=pk)
        .select_related("agent", "organization", "user")
        .first()
    )
    if not ws_number:
        raise ValueError(f"WhatsApp sender {sender_id} not found")

    sender_org = resolved_organization_for_ws_number(ws_number)
    if not sender_org or sender_org.id != organization.id:
        raise ValueError("WhatsApp sender does not belong to this organization")

    if not (ws_number.platform_id or "").strip():
        raise ValueError("WhatsApp sender is missing platform_id")

    if not accessible_agents_qs(actor).filter(pk=ws_number.agent_id).exists():
        raise ValueError("You do not have access to the agent linked to this sender")

    return ws_number


def _resolve_verified_contact(
    *,
    ws_contact_id: int | str,
    ws_number: WSNumber,
    organization: Organization,
) -> WSContact:
    try:
        pk = int(ws_contact_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid ws_contact_id: {ws_contact_id}") from exc

    contact = (
        WSContact.objects.filter(pk=pk)
        .select_related("user", "ws_number")
        .first()
    )
    if not contact:
        raise ValueError(f"WhatsApp contact {ws_contact_id} not found")
    if contact.ws_number_id != ws_number.id:
        raise ValueError("WhatsApp contact does not belong to this sender")
    if not contact.user_id:
        raise ValueError(
            "WhatsApp contact is not verified (no linked organization member)"
        )

    target_user = contact.user
    if not user_belongs_to_organization(target_user, organization):
        raise ValueError(
            "Linked user is not a member of this organization"
        )
    active_ids = {u.id for u in iter_organization_member_users(organization)}
    if target_user.id not in active_ids:
        raise ValueError(
            "Linked user is not an active organization member"
        )
    return contact


def build_template_components(
    template: WhatsAppTemplateDefinition,
    variables: TemplateVariables,
    *,
    source_conversation_id: str | None,
) -> list[dict[str, Any]]:
    """Build Meta Cloud API template components from validated variables."""
    body_values = list(variables.body or [])
    if len(body_values) != template.body_variable_count:
        raise ValueError(
            f"Template '{template.id}' expects {template.body_variable_count} "
            f"body variable(s), got {len(body_values)}"
        )

    components: list[dict[str, Any]] = []
    if body_values:
        components.append(
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(v)} for v in body_values
                ],
            }
        )

    button_defs = list(template.buttons)
    if not button_defs:
        if variables.buttons:
            raise ValueError(
                f"Template '{template.id}' does not accept button variables"
            )
        return components

    auto_count = sum(1 for b in button_defs if b.use_source_conversation_id)
    manual_count = len(button_defs) - auto_count
    provided_buttons = list(variables.buttons or [])

    if variables.buttons is not None and len(provided_buttons) != manual_count:
        raise ValueError(
            f"Template '{template.id}' expects {manual_count} button "
            f"variable(s), got {len(provided_buttons)}"
        )
    if variables.buttons is None and manual_count > 0:
        raise ValueError(
            f"Template '{template.id}' expects {manual_count} button variable(s)"
        )

    manual_iter = iter(provided_buttons)
    for btn in button_defs:
        if btn.use_source_conversation_id:
            if not source_conversation_id:
                raise ValueError(
                    "This template requires source_conversation_id for the URL button"
                )
            value = str(source_conversation_id)
        else:
            value = str(next(manual_iter))
        components.append(
            {
                "type": "button",
                "sub_type": btn.sub_type,
                "index": str(btn.index),
                "parameters": [{"type": "text", "text": value}],
            }
        )

    return components


def get_or_create_delivery_conversation(
    ws_number: WSNumber,
    phone_digits: str,
    *,
    ws_contact: WSContact | None = None,
) -> Conversation:
    """
    Prefer the active WhatsApp thread; if only historical (inactive) contact
    exists, open a new active delivery conversation.
    """
    phone = _digits_only(phone_digits)
    active = get_active_whatsapp_conversation(ws_number, phone)
    if active:
        contact = ws_contact or active.ws_contact
        if active.ws_contact_id is None and contact is not None:
            active.ws_contact = contact
            active.save(update_fields=["ws_contact", "updated_at"])
        return active
    # Contact rows are created on inbound; existence implies prior contact.
    if ws_contact is None:
        ws_contact = WSContact.objects.filter(
            ws_number=ws_number, number=phone
        ).first()
    if ws_contact is None:
        raise ValueError(
            "This phone number has never contacted this WhatsApp sender"
        )
    return create_whatsapp_conversation(ws_number, phone)


def send_ws_template_to_member(
    *,
    actor_user_id: int,
    organization_id,
    sender_id: int | str,
    ws_contact_id: int | str,
    template_id: str,
    template_variables: TemplateVariables | dict[str, Any],
    source_conversation_id: str | None,
) -> SendWsTemplateResult:
    actor = User.objects.filter(pk=actor_user_id).first()
    if not actor:
        raise ValueError("Authenticated actor not found")

    organization = Organization.objects.filter(pk=organization_id).first()
    if not organization:
        raise ValueError("Organization not found")

    if not user_belongs_to_organization(actor, organization):
        raise ValueError("Actor is not a member of this organization")

    template = get_template(template_id)
    if not template:
        raise ValueError(
            f"Unknown or disabled WhatsApp template id: {template_id}"
        )

    if isinstance(template_variables, TemplateVariables):
        variables = template_variables
    else:
        variables = TemplateVariables.model_validate(template_variables or {})

    ws_number = _resolve_sender(
        sender_id=sender_id,
        organization=organization,
        actor=actor,
    )
    contact = _resolve_verified_contact(
        ws_contact_id=ws_contact_id,
        ws_number=ws_number,
        organization=organization,
    )
    phone_digits = contact.number

    components = build_template_components(
        template,
        variables,
        source_conversation_id=source_conversation_id,
    )

    delivery_conversation = get_or_create_delivery_conversation(
        ws_number,
        phone_digits,
        ws_contact=contact,
    )

    try:
        wamid = send_template_message(
            ws_number.platform_id,
            phone_digits,
            template_name=template.meta_name,
            language_code=template.language_code,
            components=components or None,
        )
    except Exception as exc:
        logger.warning(
            "send_ws_template_to_member failed (sender=%s, contact=%s, template=%s): %s",
            sender_id,
            ws_contact_id,
            template_id,
            exc,
        )
        raise ValueError(f"Failed to send WhatsApp template: {exc}") from exc

    preview_body = " ".join(variables.body).strip()
    text = (
        f"[WhatsApp template:{template.id}] {preview_body}".strip()
        or f"[WhatsApp template:{template.id}]"
    )
    Message.objects.create(
        conversation=delivery_conversation,
        type="assistant",
        text=text[:4000],
        metadata={
            "whatsapp_wamid": wamid,
            "whatsapp_template_id": template.id,
            "whatsapp_template_name": template.meta_name,
            "source_conversation_id": str(source_conversation_id)
            if source_conversation_id
            else None,
            "target_user_id": contact.user_id,
            "ws_contact_id": contact.id,
        },
    )

    return SendWsTemplateResult(
        sent=True,
        message=f"Template '{template.id}' sent to {phone_digits}.",
        wamid=wamid,
        delivery_conversation_id=str(delivery_conversation.id),
        template_id=template.id,
        target_phone=phone_digits,
        ws_contact_id=contact.id,
    )
