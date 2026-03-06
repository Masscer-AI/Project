"""
Tool: read_plugin_instructions

Lets the agent fetch detailed formatting/usage instructions for a
frontend rendering plugin (e.g. mermaid-diagrams, document-maker)
on demand, instead of always injecting them into the system prompt.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.ai_layers.plugins.registry import (
    PLUGIN_DEFINITIONS,
    _read_plugin_instructions,
)


class ReadPluginInstructionsParams(BaseModel):
    slug: str = Field(
        description=(
            "The plugin slug to fetch instructions for. "
            "Available slugs: "
            + ", ".join(sorted(PLUGIN_DEFINITIONS.keys()))
        )
    )


class ReadPluginInstructionsResult(BaseModel):
    found: bool
    slug: str
    name: str = ""
    instructions: str = ""


def read_plugin_instructions(slug: str) -> ReadPluginInstructionsResult:
    plugin = PLUGIN_DEFINITIONS.get(slug)
    if not plugin:
        available = ", ".join(sorted(PLUGIN_DEFINITIONS.keys()))
        return ReadPluginInstructionsResult(
            found=False,
            slug=slug,
            instructions=f"Unknown plugin '{slug}'. Available: {available}",
        )

    instructions = _read_plugin_instructions(slug)
    return ReadPluginInstructionsResult(
        found=True,
        slug=slug,
        name=plugin.name,
        instructions=instructions,
    )


def get_tool(**kwargs) -> dict:
    return {
        "name": "read_plugin_instructions",
        "description": (
            "Fetch the detailed formatting instructions for a frontend "
            "rendering plugin (e.g. mermaid-diagrams for diagrams, "
            "document-maker for formal HTML documents). Call this before "
            "using a plugin so you follow the correct syntax."
        ),
        "parameters": ReadPluginInstructionsParams,
        "function": read_plugin_instructions,
    }
