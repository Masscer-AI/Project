"""Catalog of known external MCP server presets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MCPExternalCatalogEntry:
    key: str
    name: str
    description: str
    docs_url: str
    transport: str
    command: str
    args: tuple[str, ...]
    env: dict[str, str]
    default_remote_tool_names: tuple[str, ...]


WEATHER_MCP_BASIC_TOOLS: tuple[str, ...] = (
    "get_weather_summary",
    "get_forecast",
    "get_current_conditions",
    "get_alerts",
    "search_location",
    "check_service_status",
)

WEATHER_MCP_CATALOG = MCPExternalCatalogEntry(
    key="weather-mcp",
    name="Weather MCP",
    description=(
        "Live weather data via NOAA and Open-Meteo — forecasts, alerts, "
        "air quality, and more. No API keys required."
    ),
    docs_url="https://github.com/weather-mcp/weather-mcp",
    transport="stdio",
    command="npx",
    args=("-y", "@dangahagan/weather-mcp@latest"),
    env={"ENABLED_TOOLS": "basic"},
    default_remote_tool_names=WEATHER_MCP_BASIC_TOOLS,
)

MCP_EXTERNAL_CATALOG: dict[str, MCPExternalCatalogEntry] = {
    WEATHER_MCP_CATALOG.key: WEATHER_MCP_CATALOG,
}


def get_catalog_entry(key: str) -> MCPExternalCatalogEntry | None:
    return MCP_EXTERNAL_CATALOG.get(key)


def list_catalog_entries() -> list[MCPExternalCatalogEntry]:
    return list(MCP_EXTERNAL_CATALOG.values())


def catalog_entry_to_dict(entry: MCPExternalCatalogEntry) -> dict:
    return {
        "key": entry.key,
        "name": entry.name,
        "description": entry.description,
        "docs_url": entry.docs_url,
        "transport": entry.transport,
        "default_remote_tool_names": list(entry.default_remote_tool_names),
    }
