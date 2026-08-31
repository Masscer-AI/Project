from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Dict, Any, Optional, Literal


class Alert(BaseModel):
    """Schema para una alerta levantada por la IA."""
    
    id: str = Field(
        description="ID (UUID) de la alert rule que se levanta"
    )
    extractions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Datos extraídos de la conversación según los requerimientos de la alert rule"
    )


class ConversationAnalysisResult(BaseModel):
    """Schema para el resultado del análisis de una conversación con detección de alertas."""
    
    reasoning: str = Field(
        description="Explicación de por qué la conversación levanta o no una o varias alertas"
    )
    alerts: list[Alert] = Field(
        default_factory=list,
        description="Lista de alertas que se deben levantar para esta conversación"
    )


class ChatWidgetStyle(BaseModel):
    primary_color: Optional[str] = Field(
        default=None,
        pattern=r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
        description="Primary color in hex format (#RGB or #RRGGBB)",
    )
    theme: Optional[Literal["default", "light", "dark"]] = Field(
        default=None,
        description="Widget theme mode",
    )
    show_history: bool = Field(
        default=False,
        description="When true, show previous chats (list + back); when false, skip history UI",
    )
    allow_visitor_attachments: bool = Field(
        default=False,
        description="When true, visitors may upload files and send input_attachment in agent-task payloads",
    )


class ChatWidgetCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        description="Internal tool name, e.g. read_attachment",
    )
    type: Literal["internal_tool"] = Field(
        default="internal_tool",
        description="Capability type",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this capability is enabled",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Capability name cannot be blank")
        return cleaned


class ChatWidgetCapabilitiesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: list[ChatWidgetCapability] = Field(default_factory=list)

    @field_validator("capabilities")
    @classmethod
    def validate_unique_capability_names(cls, value: list[ChatWidgetCapability]):
        names = [cap.name for cap in value]
        if len(names) != len(set(names)):
            raise ValueError("Capability names must be unique")
        return value


class ConversationRelatedAgent(BaseModel):
    """Agent reference stored on conversation metadata (avoid name clash with Django Agent)."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(description="Primary key of the Agent row")


class ConversationMetadata(BaseModel):
    """Validated shape for Conversation.metadata JSON."""

    model_config = ConfigDict(extra="forbid")

    related_agents: list[ConversationRelatedAgent] = Field(
        default_factory=list,
        description="Agents associated with this conversation UI selection, in order",
    )
    surface: Optional[Literal["compliance"]] = Field(
        default=None,
        description="Dedicated product surface this conversation belongs to",
    )
    folio_id: Optional[str] = Field(
        default=None,
        description="Compliance folio UUID when this conversation is a KYB thread",
    )


def metadata_payload_for_related_agents(
    agent_ids_in_order: list[int],
    *,
    surface: Optional[Literal["compliance"]] = None,
    existing: Optional[dict] = None,
) -> dict:
    """Build validated ``Conversation.metadata`` for UI agent selection (send order)."""
    resolved_surface = surface
    folio_id = None
    if isinstance(existing, dict):
        if resolved_surface is None:
            raw_surface = existing.get("surface")
            if raw_surface == "compliance":
                resolved_surface = "compliance"
        raw_folio = existing.get("folio_id")
        if raw_folio:
            folio_id = str(raw_folio)
    meta = ConversationMetadata(
        related_agents=[ConversationRelatedAgent(id=aid) for aid in agent_ids_in_order],
        surface=resolved_surface,
        folio_id=folio_id,
    )
    return meta.model_dump(mode="json", exclude_none=True)


def compliance_conversation_metadata(
    agent_id: int, *, folio_id: Optional[str] = None, existing: Optional[dict] = None
) -> dict:
    """Metadata for the sticky per-user compliance assistant thread."""
    merged = dict(existing) if isinstance(existing, dict) else {}
    if folio_id:
        merged["folio_id"] = folio_id
    return metadata_payload_for_related_agents(
        [agent_id], surface="compliance", existing=merged
    )


class ConversationTakeoverMetadata(BaseModel):
    """Validated shape for ConversationTakeover.metadata JSON."""

    model_config = ConfigDict(extra="forbid")

    ended_reason: Optional[str] = Field(
        default=None,
        description="Why the takeover ended (e.g. manual_release, inactivity_timeout)",
    )


def takeover_metadata_payload(**fields) -> dict:
    """Build validated takeover metadata; omit unset optional fields."""
    meta = ConversationTakeoverMetadata(**fields)
    return meta.model_dump(mode="json", exclude_none=True)

