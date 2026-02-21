"""
Pydantic schemas for ai_layers (AgentSession, etc.).

Validates and documents structures used across the module. Reusable for other schemas.
"""

from typing import Any, Literal, Union
from pydantic import BaseModel, Field


# ---- Reusable refs ----

class AgentRef(BaseModel):
    id: int
    slug: str
    name: str


class ModelRef(BaseModel):
    id: int
    slug: str
    provider: str


# ---- User inputs (discriminated union) ----

class UserInputText(BaseModel):
    type: Literal["input_text"] = "input_text"
    text: str


class UserInputAttachment(BaseModel):
    type: Literal["input_attachment"] = "input_attachment"
    attachment_id: str


class UserInputOther(BaseModel):
    """Catch-all for future input types. Extend Union when adding new typed variants."""

    type: str
    model_config = {"extra": "allow"}


UserInput = Union[UserInputText, UserInputAttachment, UserInputOther]


# ---- Prev messages ----

class PrevMessage(BaseModel):
    type: Literal["user", "assistant"]
    id: int | None = None
    text: str
    versions: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)


# ---- AgentSession inputs ----

class AgentSessionInputs(BaseModel):
    """Inputs to an agent session. Validated before persisting."""

    instructions: str = Field(description="Full system prompt")
    user_inputs: list[UserInput] = Field(
        default_factory=list,
        description="Raw user inputs",
    )
    user_message_text: str = Field(description="Resolved plain text for the LLM")
    tool_names: list[str] = Field(default_factory=list, description="Enabled tool names")
    plugin_slugs: list[str] = Field(
        default_factory=list,
        description="Enabled plugin slugs (server-side allowlist)",
    )
    agent: AgentRef = Field(description="Agent reference")
    model: ModelRef = Field(description="Model reference")
    multiagentic_modality: Literal["isolated", "grupal"] = "isolated"
    prev_messages: list[PrevMessage] = Field(
        default_factory=list,
        description="Previous conversation messages for context reproducibility",
    )
    max_iterations: int = Field(default=10, ge=1, le=100)


# ---- Output schemas ----

class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OutputValue(BaseModel):
    """Structured output: string or JSON."""

    type: Literal["string", "json"]
    value: str | dict[str, Any]


class OutputError(BaseModel):
    """Error details when status is error."""

    message: str
    traceback: str = ""


class AgentSessionOutputs(BaseModel):
    """Outputs from an agent session. Validated before persisting."""

    messages: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Full message list from AgentLoop (user, tool_calls, tool_outputs, assistant)",
    )
    output: OutputValue = Field(description="Final output as string or structured JSON")
    usage: Usage = Field(default_factory=Usage)
    status: Literal["completed", "error"] = "completed"
    error: OutputError | None = Field(default=None, description="Set when status is error")


# ---- Task type ----

TASK_TYPE_CHAT_MESSAGE = "chat_message"
