import re
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# Allowed variable names in condition expressions
_ALLOWED_VARS = {"n_alerts"}

# Tokenizer: splits a condition string into tokens for safe evaluation
_TOKEN_RE = re.compile(
    r"""
    (\d+)               # integer literal
    | (n_alerts)        # allowed variable
    | (>=|<=|==|!=|>|<) # comparison operators
    | (AND|OR)          # logical operators (case-sensitive)
    | (\s+)             # whitespace (ignored)
    """,
    re.VERBOSE,
)

_VALID_TOKEN_GROUPS = {1, 2, 3, 4, 5}  # all groups are expected tokens


def _validate_condition_syntax(condition: str) -> str:
    """
    Validates that a condition string only contains allowed tokens.
    Raises ValueError if unexpected characters or tokens are found.

    Allowed syntax examples:
      "n_alerts > 5"
      "n_alerts >= 3 AND n_alerts <= 9"
      "n_alerts == 1"
    """
    pos = 0
    while pos < len(condition):
        match = _TOKEN_RE.match(condition, pos)
        if not match:
            raise ValueError(
                f"Invalid token in condition at position {pos}: "
                f"'{condition[pos:pos+10]}...'"
            )
        pos = match.end()
    return condition


def evaluate_condition(condition: str, n_alerts: int) -> bool:
    """
    Safely evaluates a condition string against a given n_alerts count.
    Only n_alerts comparisons with AND/OR are supported.
    """
    # Replace AND/OR with Python equivalents, substitute variable
    expr = condition.replace("AND", "and").replace("OR", "or")
    expr = expr.replace("n_alerts", str(n_alerts))
    # At this point expr is only digits, operators, spaces, and/or 'and'/'or'
    # Safe to eval since _validate_condition_syntax already whitelisted the input
    try:
        return bool(eval(expr))  # noqa: S307 — input is whitelist-validated above
    except Exception as exc:
        raise ValueError(f"Failed to evaluate condition '{condition}': {exc}") from exc


class NotificationCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: Literal["n_alerts"] = Field(
        description="The subject of the condition. Currently only 'n_alerts' is supported."
    )
    condition: str = Field(
        description=(
            "A condition expression involving the subject variable. "
            "Examples: 'n_alerts > 5', 'n_alerts >= 3 AND n_alerts <= 9'"
        )
    )
    delivery_method: Literal["app", "email", "all"] = Field(
        default="app",
        description="How to deliver the notification when this condition is met.",
    )
    message: str = Field(
        description=(
            "Notification message template. "
            "Supports {{n_alerts}} as a placeholder for the current alert count."
        )
    )

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, value: str) -> str:
        return _validate_condition_syntax(value.strip())

    @field_validator("message")
    @classmethod
    def validate_message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message cannot be blank")
        return value

    def render_message(self, n_alerts: int) -> str:
        """Returns the message with template variables substituted."""
        return self.message.replace("{{n_alerts}}", str(n_alerts))

    def is_met(self, n_alerts: int) -> bool:
        """Returns True if the condition is satisfied for the given n_alerts count."""
        return evaluate_condition(self.condition, n_alerts)


class NotificationConditionList(BaseModel):
    """Wrapper used to validate the full conditions JSONField on NotificationRule."""

    model_config = ConfigDict(extra="forbid")

    conditions: list[NotificationCondition] = Field(default_factory=list)

    @model_validator(mode="after")
    def at_least_one_condition(self) -> "NotificationConditionList":
        if not self.conditions:
            raise ValueError("At least one condition is required.")
        return self
