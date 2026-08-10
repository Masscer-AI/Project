"""
Tool: send_ws_template_message

Send an allowlisted WhatsApp Cloud API template to a verified WhatsApp contact
(linked organization member) on a sender line assigned to the current agent.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from api.whatsapp.template_send import (
    SendWsTemplateResult,
    TemplateVariables,
    send_ws_template_to_member,
)


class SendWsTemplateMessageParams(BaseModel):
    sender_id: int = Field(
        description="WhatsApp sender_id from list_whatsapp_resources."
    )
    ws_contact_id: int = Field(
        description=(
            "Verified contact ws_contact_id from list_whatsapp_resources "
            "(contact must be linked to an organization member)."
        )
    )
    template_id: str = Field(
        description="Local template_id from list_whatsapp_templates."
    )
    # Do not attach Field(description=...) here. Pydantic represents this nested
    # model with $ref, and OpenAI rejects schema nodes that combine $ref with
    # sibling keywords such as description.
    template_variables: TemplateVariables = Field(default_factory=TemplateVariables)


def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    organization_id=None,
    agent_id: int | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError(
            "send_ws_template_message requires conversation_id in tool context"
        )
    if user_id is None:
        raise ValueError(
            "send_ws_template_message requires user_id in tool context"
        )
    if not isinstance(user_id, int):
        raise ValueError(
            "send_ws_template_message requires an authenticated web user"
        )
    if organization_id is None:
        raise ValueError(
            "send_ws_template_message requires organization_id in tool context"
        )
    if agent_id is None:
        raise ValueError(
            "send_ws_template_message requires agent_id in tool context"
        )

    def send_ws_template_message(
        sender_id: int,
        ws_contact_id: int,
        template_id: str,
        template_variables: TemplateVariables | dict[str, Any] | None = None,
    ) -> SendWsTemplateResult:
        return send_ws_template_to_member(
            actor_user_id=user_id,
            organization_id=organization_id,
            agent_id=agent_id,
            sender_id=sender_id,
            ws_contact_id=ws_contact_id,
            template_id=template_id,
            template_variables=template_variables or {},
            source_conversation_id=conversation_id,
        )

    return {
        "name": "send_ws_template_message",
        "description": (
            "Send an approved WhatsApp template message to a verified WhatsApp "
            "contact (organization member linked to a phone on a sender line "
            "assigned to you). The template is recorded on that contact's "
            "**active WhatsApp conversation** so their reply (text or quick-reply "
            "button) continues in that thread. "
            "Use list_whatsapp_resources for sender_id and ws_contact_id, and "
            "list_whatsapp_templates for template_id and required variables. "
            "For templates with a conversation URL button, the current conversation "
            "id is used automatically — leave buttons null/omitted. "
            "For templates with header_type=image, set "
            "header_image_attachment_id to a MessageAttachment UUID (image) "
            "from the current conversation."
        ),
        "parameters": SendWsTemplateMessageParams,
        "function": send_ws_template_message,
    }
