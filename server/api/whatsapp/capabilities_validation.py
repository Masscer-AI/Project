"""Validate WSNumber.capabilities using the same rules as chat widget tools."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError as PydanticValidationError
from rest_framework import serializers

from api.ai_layers.tools import list_available_tools
from api.messaging.schemas import ChatWidgetCapabilitiesPayload

from .capability_tools import WHATSAPP_ALLOWED_CAPABILITY_TOOLS, filter_capabilities_for_whatsapp


def validate_whatsapp_capabilities_list(value: Any) -> list[dict[str, Any]]:
    """
    Normalize and validate a capabilities JSON list (internal tools only).

    Raises ``serializers.ValidationError`` on invalid input (same contract as
    ``ChatWidgetSerializer.validate_capabilities``).
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise serializers.ValidationError("capabilities must be a JSON array.")

    try:
        parsed_payload = ChatWidgetCapabilitiesPayload.model_validate(
            {"capabilities": value}
        )
    except PydanticValidationError as exc:
        raise serializers.ValidationError(exc.errors()) from exc

    available_tools = set(list_available_tools())
    invalid_names = sorted(
        cap.name
        for cap in parsed_payload.capabilities
        if cap.name not in available_tools
    )
    if invalid_names:
        raise serializers.ValidationError(
            f"Unknown capabilities: {', '.join(invalid_names)}"
        )

    disallowed = sorted(
        cap.name
        for cap in parsed_payload.capabilities
        if cap.name not in WHATSAPP_ALLOWED_CAPABILITY_TOOLS
    )
    if disallowed:
        raise serializers.ValidationError(
            f"Capabilities not available on WhatsApp: {', '.join(disallowed)}"
        )

    dumped = [cap.model_dump() for cap in parsed_payload.capabilities]
    return filter_capabilities_for_whatsapp(dumped)
