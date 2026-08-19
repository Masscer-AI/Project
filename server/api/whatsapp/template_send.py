"""
Scoped WhatsApp template delivery for organization-member tooling.

Security invariants:
- Template id must be in the local allowlist.
- Sender must be a WSNumber in the actor's organization assigned to the
  calling agent (the agent currently running the turn).
- Target must be a WSContact on that sender with user linked to an active org member.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from django.contrib.auth.models import User
from pydantic import BaseModel, ConfigDict, Field

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
from api.whatsapp.template_access import get_template_for_organization
from api.whatsapp.template_registry import (
    WhatsAppTemplateDefinition,
    fill_template_placeholders,
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
    header_image_attachment_id: str | None = Field(
        default=None,
        description=(
            "MessageAttachment UUID of an image in the current conversation. "
            "Required for templates with header_type=image (e.g. from an "
            "uploaded/inbound image the user attached)."
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
    agent_id: int,
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

    if ws_number.agent_id != agent_id:
        raise ValueError(
            "WhatsApp sender is not assigned to the current agent"
        )

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

def resolve_header_image_from_attachment(
    *,
    attachment_id: str,
    conversation_id: str | None,
    phone_number_id: str,
) -> dict[str, Any]:
    """
    Resolve a MessageAttachment UUID into a Meta template header image param.

    Prefers a public HTTPS link; falls back to uploading bytes to WhatsApp media.
    """
    from api.messaging.attachment_urls import absolute_file_url_for_attachment
    from api.messaging.models import MessageAttachment
    from api.whatsapp.outbound_media import (
        read_attachment_file_bytes,
        upload_whatsapp_media,
        whatsapp_media_type_for_attachment,
    )

    att_id = (attachment_id or "").strip()
    if not att_id:
        raise ValueError("header_image_attachment_id is required")
    if not conversation_id:
        raise ValueError(
            "header_image_attachment_id requires the current conversation context"
        )

    try:
        att = MessageAttachment.objects.get(id=att_id)
    except (MessageAttachment.DoesNotExist, ValueError, TypeError) as exc:
        raise ValueError(
            f"Attachment '{att_id}' not found"
        ) from exc

    if str(att.conversation_id) != str(conversation_id):
        raise ValueError(
            f"Attachment '{att_id}' does not belong to this conversation"
        )

    wa_type = whatsapp_media_type_for_attachment(att)
    if wa_type != "image":
        raise ValueError(
            f"Attachment '{att_id}' must be an image for the template header"
        )

    link = absolute_file_url_for_attachment(att)
    if link and link.startswith("https://"):
        return {"link": link}

    file_bytes, mime_type, filename = read_attachment_file_bytes(att)
    media_id = upload_whatsapp_media(
        phone_number_id,
        file_bytes=file_bytes,
        mime_type=mime_type,
        wa_type="image",
        filename=filename,
    )
    return {"id": media_id}

def build_template_components(
    template: WhatsAppTemplateDefinition,
    variables: TemplateVariables,
    *,
    source_conversation_id: str | None,
    header_image: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build Meta Cloud API template components from validated variables."""
    body_values = list(variables.body or [])
    if len(body_values) != template.body_variable_count:
        raise ValueError(
            f"Template '{template.id}' expects {template.body_variable_count} "
            f"body variable(s), got {len(body_values)}"
        )

    has_header_att = bool((variables.header_image_attachment_id or "").strip())
    if template.header_type != "image" and has_header_att:
        raise ValueError(
            f"Template '{template.id}' does not accept a header image"
        )
    if template.header_type == "image" and not header_image:
        raise ValueError(
            "This template requires header_image_attachment_id "
            "(MessageAttachment UUID of an image in the current conversation)"
        )

    components: list[dict[str, Any]] = []
    if template.header_type == "image" and header_image:
        components.append(
            {
                "type": "header",
                "parameters": [{"type": "image", "image": header_image}],
            }
        )

    if body_values:
        components.append(
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(v)} for v in body_values
                ],
            }
        )

    url_button_defs = [b for b in template.buttons if b.sub_type == "url"]
    if not url_button_defs:
        if variables.buttons:
            raise ValueError(
                f"Template '{template.id}' does not accept button variables"
            )
        return components

    auto_count = sum(1 for b in url_button_defs if b.use_source_conversation_id)
    manual_count = len(url_button_defs) - auto_count
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
    for btn in url_button_defs:
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
                "sub_type": "url",
                "index": str(btn.index),
                "parameters": [{"type": "text", "text": value}],
            }
        )

    return components

def format_template_delivery_message(
    template: WhatsAppTemplateDefinition,
    variables: TemplateVariables,
    *,
    source_conversation_id: str | None,
) -> str:
    """
    Markdown stored on the WhatsApp delivery conversation.

    Interpolates the approved Meta copy (header/body/footer/buttons) so the
    stored message looks like what was sent, plus a source-conversation link.
    """
    body_values = [str(v) for v in (variables.body or [])]
    lines = ["---"]
    if source_conversation_id:
        lines.append(
            f"[Send from another conversation](/chat?conversation={source_conversation_id})"
        )
        lines.append("")
    if template.header_text:
        lines.append(
            f"### {fill_template_placeholders(template.header_text, body_values)}"
        )
        lines.append("")
    if template.body_text:
        lines.append(
            fill_template_placeholders(template.body_text, body_values).strip()
        )
    else:
        filled = [v.strip() for v in body_values if str(v).strip()]
        if filled:
            lines.append("\n\n".join(filled))
    if template.footer_text:
        lines.append("")
        lines.append(
            fill_template_placeholders(template.footer_text, body_values).strip()
        )
    if template.buttons:
        lines.append("")
        manual_button_suffixes = iter(str(v) for v in (variables.buttons or []))
        for btn in template.buttons:
            label = (btn.label or "").strip()
            if not label:
                continue
            href = ""
            if btn.sub_type == "url" and btn.url:
                suffix = ""
                if btn.use_source_conversation_id and source_conversation_id:
                    suffix = str(source_conversation_id)
                elif not btn.use_source_conversation_id:
                    suffix = str(next(manual_button_suffixes, ""))
                href = f"{btn.url}{suffix}"
            if href:
                lines.append(f"- [{label}]({href})")
            else:
                lines.append(f"- {label}")
    lines.append("")
    lines.append("---")
    return "\n".join(lines)[:4000]

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
    agent_id: int,
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

    try:
        resolved_agent_id = int(agent_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid agent_id: {agent_id}") from exc

    template = get_template_for_organization(template_id, organization)
    if not template:
        raise ValueError(
            f"Unknown, disabled, or unavailable WhatsApp template id: {template_id}"
        )

    if isinstance(template_variables, TemplateVariables):
        variables = template_variables
    else:
        variables = TemplateVariables.model_validate(template_variables or {})

    ws_number = _resolve_sender(
        sender_id=sender_id,
        organization=organization,
        agent_id=resolved_agent_id,
    )
    contact = _resolve_verified_contact(
        ws_contact_id=ws_contact_id,
        ws_number=ws_number,
        organization=organization,
    )
    phone_digits = contact.number

    header_image: dict[str, Any] | None = None
    if template.header_type == "image":
        header_image = resolve_header_image_from_attachment(
            attachment_id=variables.header_image_attachment_id or "",
            conversation_id=source_conversation_id,
            phone_number_id=ws_number.platform_id,
        )

    components = build_template_components(
        template,
        variables,
        source_conversation_id=source_conversation_id,
        header_image=header_image,
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

    text = format_template_delivery_message(
        template,
        variables,
        source_conversation_id=source_conversation_id,
    )

    assistant_msg = Message.objects.create(
        conversation=delivery_conversation,
        type="assistant",
        text=text,
        metadata={
            "whatsapp_wamid": wamid,
            "whatsapp_template_id": template.id,
            "whatsapp_template_name": template.meta_name,
            "source_conversation_id": str(source_conversation_id)
            if source_conversation_id
            else None,
            "target_user_id": contact.user_id,
            "ws_contact_id": contact.id,
            "delivery_conversation_id": str(delivery_conversation.id),
        },
    )
    try:
        from api.messaging.takeover import emit_message_created

        emit_message_created(None, delivery_conversation, assistant_msg)
    except Exception:
        logger.exception(
            "emit_message_created failed after template send conversation=%s",
            delivery_conversation.id,
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
