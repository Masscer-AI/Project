"""
LLM-assisted draft for NotificationRule (natural language → conditions + alert_rule_id).

Uses create_structured_completion (sync OpenAI Responses API). Output is validated
with NotificationConditionList before returning to the client.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.messaging.models import ConversationAlertRule
from api.notify.schemas import NotificationConditionList
from api.utils.openai_functions import create_structured_completion

logger = logging.getLogger(__name__)

DEFAULT_BUILD_MODEL = os.environ.get("NOTIFICATION_RULE_BUILD_MODEL", "gpt-4o-mini")


class NotificationConditionBuildItem(BaseModel):
    """Matches OpenAI strict schema; validated again via NotificationCondition."""

    model_config = ConfigDict(extra="forbid")

    subject: Literal["n_alerts"] = "n_alerts"
    condition: str = Field(
        ...,
        description="e.g. n_alerts > 5 or n_alerts >= 3 AND n_alerts <= 9",
    )
    delivery_method: Literal["app", "email", "all"] = "app"
    message: str = Field(..., description="Must include {{n_alerts}} for the count.")

    @field_validator("condition", "message")
    @classmethod
    def strip_nonempty(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("must not be empty")
        return s


class NotificationRuleBuildLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_rule_id: str = Field(
        ...,
        description="UUID of the ConversationAlertRule to attach this notification to.",
    )
    conditions: list[NotificationConditionBuildItem] = Field(
        ...,
        min_length=1,
        description="At least one notification condition.",
    )
    assistant_summary: str = Field(
        ...,
        description="Short explanation for the user (same language as the request when possible).",
    )


def _serialize_alert_rules_for_prompt(rules: list[ConversationAlertRule]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rules:
        out.append(
            {
                "id": str(r.id),
                "name": r.name,
                "trigger": r.trigger,
                "extractions": r.extractions or {},
            }
        )
    return out


def _serialize_existing_notification_rules(
    organization_id,
    alert_rule_id: UUID | None = None,
) -> list[dict[str, Any]]:
    from api.notify.models import NotificationRule

    qs = NotificationRule.objects.filter(organization_id=organization_id).select_related(
        "alert_rule"
    )
    if alert_rule_id is not None:
        qs = qs.filter(alert_rule_id=alert_rule_id)
    rows = qs.order_by("-created_at")[:30]
    return [
        {
            "alert_rule_id": str(nr.alert_rule_id),
            "alert_rule_name": nr.alert_rule.name if nr.alert_rule_id else None,
            "enabled": nr.enabled,
            "conditions_preview": [c.get("condition", "") for c in (nr.conditions or [])],
        }
        for nr in rows
    ]


BUILD_SYSTEM_PROMPT = """You configure notification rules for a team dashboard.

Context:
- An **alert rule** (ConversationAlertRule) defines when a "problem" is raised from a chat. The user has already selected which alert rule this notification applies to.
- A **notification rule** watches how many **actionable** open alerts exist for that alert rule, and notifies people when a numeric condition is met.
- The variable is always **n_alerts**: the count of alerts for that alert rule whose status is still actionable (pending team work). Use only this variable in conditions.

You must:
1. Set **alert_rule_id** to exactly the id string shown in the JSON (the user-selected rule). Do not change it.
2. Produce one or more **conditions**. Each condition has:
   - subject: always the string "n_alerts"
   - condition: a safe expression using only n_alerts, integers, comparisons (>, <, >=, <=, ==, !=), AND, OR. Examples: "n_alerts > 5", "n_alerts >= 5", "n_alerts >= 3 AND n_alerts <= 10"
   - delivery_method: "app", "email", or "all"
   - message: a short user-facing template that MUST include the placeholder {{n_alerts}} where the count should appear.

If the user asks to be notified when "there are 5" or "when we reach 5", prefer **n_alerts >= 5** so the notification fires once the backlog reaches five.

3. **assistant_summary**: Briefly explain what you configured (same language as the user when possible).

Do not invent alert_rule_ids. Do not use variables other than n_alerts."""


def run_notification_rule_build(
    *,
    user_prompt: str,
    organization_id: UUID,
    alert_rule_id: UUID,
) -> dict[str, Any]:
    """
    Returns a dict safe to JSON-serialize: alert_rule_id, alert_rule_name, conditions, assistant_summary.

    Raises ValueError for validation issues (caller maps to 400).
    """
    user_prompt = (user_prompt or "").strip()
    if not user_prompt:
        raise ValueError("prompt is required")

    try:
        rule = ConversationAlertRule.objects.get(
            id=alert_rule_id,
            organization_id=organization_id,
            enabled=True,
        )
    except ConversationAlertRule.DoesNotExist:
        raise ValueError(
            "Alert rule not found, not enabled, or does not belong to your organization."
        ) from None

    rules = [rule]
    rules_payload = _serialize_alert_rules_for_prompt(rules)
    existing_payload = _serialize_existing_notification_rules(organization_id, alert_rule_id=alert_rule_id)

    user_message = f"""User request:
{user_prompt}

Selected alert rule (use this id in your output):
{json.dumps(rules_payload, ensure_ascii=False, indent=2)}

Existing notification rules for this alert rule (for context):
{json.dumps(existing_payload, ensure_ascii=False, indent=2)}
"""

    try:
        raw = create_structured_completion(
            model=DEFAULT_BUILD_MODEL,
            system_prompt=BUILD_SYSTEM_PROMPT,
            user_prompt=user_message,
            response_format=NotificationRuleBuildLLMOutput,
        )
    except Exception as exc:
        logger.exception("notification rule build LLM failed: %s", exc)
        raise RuntimeError("The assistant could not generate a suggestion.") from exc

    raw = NotificationRuleBuildLLMOutput.model_validate(raw)

    chosen_llm = (raw.alert_rule_id or "").strip()
    canonical_id = str(rule.id)
    if chosen_llm != canonical_id:
        logger.warning(
            "notification build: model returned alert_rule_id %r; using canonical %s",
            chosen_llm,
            canonical_id,
        )

    cond_dicts = [c.model_dump() for c in raw.conditions]
    try:
        validated = NotificationConditionList(conditions=cond_dicts)
    except Exception as exc:
        raise ValueError(f"Invalid conditions after generation: {exc}") from exc

    return {
        "alert_rule_id": canonical_id,
        "alert_rule_name": rule.name,
        "conditions": [c.model_dump(mode="json") for c in validated.conditions],
        "assistant_summary": (raw.assistant_summary or "").strip() or "Suggestion ready.",
    }
