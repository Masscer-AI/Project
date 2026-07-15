from django.urls import path
from .views import (
    AgentView,
    AgentTaskView,
    PlatformAgentTaskView,
    LanguageModelView,
    get_formatted_system_prompt,
    create_random_agent,
    agent_sessions_for_message,
    agent_session_execution_log_for_message,
    cancel_agent_task,
)
from .mcp_views import (
    mcp_list_agents,
    mcp_run_agent,
    mcp_task_result,
    mcp_download_attachment,
    mcp_credentials,
    mcp_credential_detail,
    mcp_connection_config,
    mcp_tool_presets,
)
from .mcp_external_views import (
    mcp_external_catalog,
    mcp_external_connections,
    mcp_external_connection_detail,
    mcp_external_connection_sync,
)

app_name = "ai_layers"

urlpatterns = [
    path("agents/", AgentView.as_view(), name="agents_list"),
    path("agents/<slug:slug>/", AgentView.as_view(), name="agents_single"),
    path("models/", LanguageModelView.as_view(), name="models_list"),
    path("models/<str:slug>/", LanguageModelView.as_view(), name="models_single"),
    path(
        "system_prompt/",
        get_formatted_system_prompt,
        name="get_formatted_system_prompt",
    ),
    path("agents/create/random/", create_random_agent, name="create_random_agent"),
    # Agent task endpoints (Celery-backed AgentLoop execution)
    path("agent-task/conversation/", AgentTaskView.as_view(), name="agent_task_conversation"),
    path("agent-task/platform/", PlatformAgentTaskView.as_view(), name="agent_task_platform"),
    path("agent-task/cancel/", cancel_agent_task, name="cancel_agent_task"),
    # Agent sessions for assistant message (audit/debug)
    path("agent-sessions/", agent_sessions_for_message, name="agent_sessions_for_message"),
    path(
        "agent-sessions/execution-log/",
        agent_session_execution_log_for_message,
        name="agent_session_execution_log_for_message",
    ),
    # MCP gateway (Bearer MCPClient auth — called by FastAPI MCP server)
    path("mcp/agents/", mcp_list_agents, name="mcp_list_agents"),
    path("mcp/run/", mcp_run_agent, name="mcp_run_agent"),
    path("mcp/result/<str:task_id>/", mcp_task_result, name="mcp_task_result"),
    path(
        "mcp/attachments/<uuid:attachment_id>/",
        mcp_download_attachment,
        name="mcp_download_attachment",
    ),
    # MCP credential management (user Token auth — UI)
    path("mcp/credentials/", mcp_credentials, name="mcp_credentials"),
    path(
        "mcp/credentials/<uuid:credential_id>/",
        mcp_credential_detail,
        name="mcp_credential_detail",
    ),
    path("mcp/connection-config/", mcp_connection_config, name="mcp_connection_config"),
    path("mcp/tool-presets/", mcp_tool_presets, name="mcp_tool_presets"),
    # Inbound MCP connections (Masscer agents call external MCP servers)
    path("mcp/external/catalog/", mcp_external_catalog, name="mcp_external_catalog"),
    path(
        "mcp/external/connections/",
        mcp_external_connections,
        name="mcp_external_connections",
    ),
    path(
        "mcp/external/connections/<uuid:connection_id>/",
        mcp_external_connection_detail,
        name="mcp_external_connection_detail",
    ),
    path(
        "mcp/external/connections/<uuid:connection_id>/sync/",
        mcp_external_connection_sync,
        name="mcp_external_connection_sync",
    ),
]
