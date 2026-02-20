from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class PluginDefinition:
    slug: str
    name: str
    instructions_filename: str

    def instructions_path(self) -> Path:
        return (
            Path(__file__).resolve().parent
            / "instructions"
            / self.instructions_filename
        )


PLUGIN_DEFINITIONS: dict[str, PluginDefinition] = {
    "calculator": PluginDefinition(
        slug="calculator",
        name="Calculator",
        instructions_filename="calculator.md",
    ),
    "mermaid-diagrams": PluginDefinition(
        slug="mermaid-diagrams",
        name="Mermaid Diagrams",
        instructions_filename="mermaid-diagrams.md",
    ),
    "document-maker": PluginDefinition(
        slug="document-maker",
        name="Document Maker",
        instructions_filename="document-maker.md",
    ),
}

AVAILABLE_PLUGIN_SLUGS: set[str] = set(PLUGIN_DEFINITIONS.keys())


@lru_cache(maxsize=None)
def _read_plugin_instructions(slug: str) -> str:
    plugin = PLUGIN_DEFINITIONS.get(slug)
    if not plugin:
        return ""
    path = plugin.instructions_path()
    return path.read_text(encoding="utf-8")


def get_plugins(slugs: list[str] | None) -> list[dict[str, str]]:
    """
    Resolve plugin slugs into canonical name + instruction text.
    Unknown slugs are ignored here; validate earlier (e.g. in the view).
    """
    if not slugs:
        return []

    # Preserve order, dedupe.
    seen: set[str] = set()
    normalized: list[str] = []
    for s in slugs:
        if not isinstance(s, str):
            continue
        s = s.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        normalized.append(s)

    resolved: list[dict[str, str]] = []
    for slug in normalized:
        plugin = PLUGIN_DEFINITIONS.get(slug)
        if not plugin:
            continue
        resolved.append(
            {
                "slug": plugin.slug,
                "name": plugin.name,
                "instructions": _read_plugin_instructions(plugin.slug),
            }
        )
    return resolved


def format_plugins_instruction(slugs: list[str] | None) -> str:
    """
    Format enabled plugins as a single instruction block suitable for appending
    to AgentLoop `instructions`.
    """
    plugins = get_plugins(slugs)
    if not plugins:
        return ""

    parts: list[str] = []
    parts.append("\n\n# Plugins enabled\n")

    for p in plugins:
        instructions = (p.get("instructions") or "").strip()
        parts.append(f"\n\n## {p.get('name', p.get('slug'))} (slug: {p.get('slug')})\n\n")
        if instructions:
            parts.append(instructions)
            parts.append("\n")

    return "".join(parts)

