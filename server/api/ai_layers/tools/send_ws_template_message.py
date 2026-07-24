"""
Tool: send_ws_template_message

Send an allowlisted WhatsApp Cloud API template to an organization member
who previously contacted the selected WhatsApp sender.
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
    target_user_id: int = Field(
        description="Organization member user_id from list_organization_members."
    )
    target_phone_number: str = Field(
        description=(
            "Full international phone digits (country_code + number, no +) that "
            "must be registered on the target member's phone_numbers."
        )
    )
    sender_id: int = Field(
        description="WhatsApp sender_id from list_accessible_whatsapp_senders."
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

    def send_ws_template_message(
        target_user_id: int,
        target_phone_number: str,
        sender_id: int,
        template_id: str,
        template_variables: TemplateVariables | dict[str, Any] | None = None,
    ) -> SendWsTemplateResult:
        return send_ws_template_to_member(
            actor_user_id=user_id,
            organization_id=organization_id,
            sender_id=sender_id,
            target_user_id=target_user_id,
            target_phone_number=target_phone_number,
            template_id=template_id,
            template_variables=template_variables or {},
            source_conversation_id=conversation_id,
        )

    return {
        "name": "send_ws_template_message",
        "description": (
            "Send an approved WhatsApp template message to an organization member. "
            "Use list_organization_members for target_user_id and their phone_numbers, "
            "list_accessible_whatsapp_senders for sender_id, and list_whatsapp_templates "
            "for template_id and required variables. "
            "The target phone must already have contacted that WhatsApp sender before. "
            "For templates with a conversation URL button, the current conversation id "
            "is used automatically — leave buttons null/omitted."
        ),
        "parameters": SendWsTemplateMessageParams,
        "function": send_ws_template_message,
    }
