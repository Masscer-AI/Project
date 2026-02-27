"""
Tool: raise_alert

Allows the agent to raise a conversation alert when it detects that the user's
message matches an alert rule. The agent receives alert rules in its context and
calls this tool with the matching rule ID, reasoning, and optional extractions.

Availability:
- Automatically injected when the conversation's organization has enabled alert rules
  that apply to the current agent (scope all_conversations or selected_agents).
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExtractionField(BaseModel):
    """A single extracted key-value pair from the conversation."""

    key: str = Field(description="Field name, e.g. room_type, phone, nights, check_in_date, guest_name.")
    value: str = Field(description="Extracted value as a string, e.g. 'Single', '0964105554', '2', '2026-02-28'.")


class RaiseAlertParams(BaseModel):
    """Parameters for the raise_alert tool."""

    reasoning: str = Field(
        description="Clear explanation of why this alert is being raised or updated, referencing specific content from the conversation."
    )
    extractions: list[ExtractionField] | None = Field(
        default=None,
        description=(
            "Structured data extracted from the conversation. "
            "REQUIRED when there is any extractable info (names, phone, dates, room type, number of guests, amounts, etc). "
            "Example: [{\"key\":\"room_type\",\"value\":\"Single\"},{\"key\":\"phone\",\"value\":\"0964105554\"},{\"key\":\"nights\",\"value\":\"2\"}]. "
            "For updates, include ALL previously known fields merged with any new ones. Never omit when data exists."
        ),
    )
    alert_rule_id: str | None = Field(
        default=None,
        description="UUID of the alert rule. Required for creating. Omit when updating (alert_id provided).",
    )
    title: str | None = Field(
        default=None,
        description="Optional short title for the alert. When updating, provide the new title if it should change.",
    )
    alert_id: str | None = Field(
        default=None,
        description="When provided, updates the existing alert instead of creating. Use the id from ALREADY RAISED when the user adds more info.",
    )


class RaiseAlertResult(BaseModel):
    """Result returned by raise_alert."""

    success: bool = Field(description="Whether the operation succeeded.")
    message: str = Field(description="Status message.")
    alert_id: str | None = Field(default=None, description="UUID of the created or updated alert.")
    updated: bool = Field(default=False, description="True if an existing alert was updated.")


def _fields_to_dict(fields: list[ExtractionField] | None) -> dict[str, Any]:
    """Convert a list of ExtractionField items (or raw dicts) into a plain dict."""
    if not fields:
        return {}
    result = {}
    for f in fields:
        if isinstance(f, ExtractionField):
            result[f.key] = f.value
        elif isinstance(f, dict):
            # Agent loop delivers JSON-decoded dicts at runtime instead of Pydantic objects
            key = f.get("key")
            value = f.get("value")
            if key is not None:
                result[str(key)] = str(value) if value is not None else ""
    return result


def _raise_alert_impl(
    reasoning: str,
    conversation_id: str,
    organization_id: int,
    alert_rule_id: str | None = None,
    extractions: list[ExtractionField] | None = None,
    title: str | None = None,
    alert_id: str | None = None,
) -> RaiseAlertResult:
    """
    Create or update a ConversationAlert.

    When alert_id is provided: update the existing alert's reasoning, extractions, title.
    Otherwise: create a new alert (requires alert_rule_id).
    """
    from api.messaging.models import Conversation, ConversationAlert, ConversationAlertRule

    try:
        conversation = Conversation.objects.select_related(
            "organization", "chat_widget", "chat_widget__agent"
        ).get(id=conversation_id)
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    if alert_id:
        logger.info(
            "raise_alert UPDATE called: alert_id=%s conversation=%s extractions_provided=%s title=%s",
            alert_id,
            conversation_id,
            extractions is not None,
            title,
        )

        extractions_dict = _fields_to_dict(extractions)

        # Push back if extractions are empty but the conversation likely has data
        if not extractions_dict:
            logger.warning(
                "raise_alert UPDATE: empty extractions for alert=%s — model should provide extracted fields.",
                alert_id,
            )
            return RaiseAlertResult(
                success=False,
                message=(
                    "extractions must not be empty when updating. "
                    "Re-call raise_alert with all known fields as a list of {key, value} pairs, "
                    "e.g. [{\"key\":\"room_type\",\"value\":\"Single\"},{\"key\":\"phone\",\"value\":\"0964105554\"}]."
                ),
                alert_id=alert_id,
                updated=False,
            )

        alert = ConversationAlert.objects.select_related(
            "alert_rule", "conversation"
        ).filter(
            id=alert_id,
            conversation_id=conversation_id,
            alert_rule__organization_id=organization_id,
        ).first()

        if not alert:
            raise ValueError(
                f"Alert {alert_id} not found or does not belong to this conversation"
            )

        update_fields = ["reasoning", "updated_at"]
        alert.reasoning = reasoning

        alert.extractions = extractions_dict
        update_fields.append("extractions")

        if title is not None:
            alert.title = title[:50]
            update_fields.append("title")

        if alert.status != "PENDING":
            alert.status = "PENDING"
            update_fields.append("status")

        alert.save(update_fields=update_fields)

        logger.info(
            "Alert updated: alert=%s conversation=%s extractions=%s",
            alert_id,
            conversation_id,
            extractions_dict,
        )
        return RaiseAlertResult(
            success=True,
            message=f"Alert updated for rule {alert.alert_rule.name}",
            alert_id=str(alert.id),
            updated=True,
        )

    # Create new alert
    logger.info(
        "raise_alert CREATE called: alert_rule_id=%s conversation=%s extractions_provided=%s",
        alert_rule_id,
        conversation_id,
        extractions is not None,
    )

    if not alert_rule_id:
        raise ValueError("alert_rule_id is required when creating a new alert")

    alert_rule = ConversationAlertRule.objects.filter(
        id=alert_rule_id,
        organization_id=organization_id,
        enabled=True,
    ).first()

    if not alert_rule:
        raise ValueError(
            f"Alert rule {alert_rule_id} not found, disabled, or not in this organization"
        )

    existing = ConversationAlert.objects.filter(
        conversation=conversation,
        alert_rule=alert_rule,
    ).first()

    if existing:
        return RaiseAlertResult(
            success=True,
            message=f"Alert already exists for rule {alert_rule.name} (idempotent)",
            alert_id=str(existing.id),
        )

    extractions_dict = _fields_to_dict(extractions)
    display_title = title or alert_rule.name
    if not title and extractions_dict:
        first_key = next(iter(extractions_dict.keys()), None)
        if first_key:
            val = str(extractions_dict.get(first_key, ""))[:30]
            if val:
                display_title = f"{alert_rule.name} - {val}"

    alert = ConversationAlert.objects.create(
        title=display_title[:50],
        reasoning=reasoning,
        extractions=extractions_dict,
        conversation=conversation,
        alert_rule=alert_rule,
        status="PENDING",
    )

    logger.info(
        "Alert raised: rule=%s conversation=%s alert=%s",
        alert_rule.name,
        conversation_id,
        alert.id,
    )
    return RaiseAlertResult(
        success=True,
        message=f"Alert raised for rule {alert_rule.name}",
        alert_id=str(alert.id),
    )


def get_tool(
    conversation_id: str | None = None,
    organization_id: int | None = None,
    **kwargs,
) -> dict:
    """
    Return an AgentTool dict for the raise_alert tool.

    Requires conversation_id and organization_id from resolve_tools context.
    """
    if not conversation_id or organization_id is None:
        raise ValueError("raise_alert requires conversation_id and organization_id in context")

    def raise_alert(
        reasoning: str,
        extractions: list[ExtractionField] | None = None,
        alert_rule_id: str | None = None,
        title: str | None = None,
        alert_id: str | None = None,
    ) -> RaiseAlertResult:
        return _raise_alert_impl(
            reasoning=reasoning,
            conversation_id=conversation_id,
            organization_id=organization_id,
            alert_rule_id=alert_rule_id,
            extractions=extractions,
            title=title,
            alert_id=alert_id,
        )

    return {
        "name": "raise_alert",
        "description": (
            "Raise or update an alert. CREATE: call with alert_rule_id, reasoning, and extractions. "
            "You MUST populate extractions with relevant data from the conversation (names, dates, amounts, issues). "
            "UPDATE: use alert_id with updated reasoning and extractions when the user adds more info. "
            "Do not raise alerts for rules that do not match."
        ),
        "parameters": RaiseAlertParams,
        "function": raise_alert,
    }
