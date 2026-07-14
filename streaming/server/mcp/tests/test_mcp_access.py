"""Tests for MCP helper modules."""

from api.ai_layers.mcp_access import sanitize_mcp_tool_name


def test_sanitize_mcp_tool_name_hyphens():
    assert sanitize_mcp_tool_name("sales-bot") == "ask_sales_bot"
