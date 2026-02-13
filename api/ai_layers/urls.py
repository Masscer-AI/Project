from django.urls import path
from .views import (
    AgentView,
    AgentTaskView,
    LanguageModelView,
    get_formatted_system_prompt,
    create_random_agent,
)
from .mcp_views import mcp_server_handler, get_mcp_config_json

app_name = "ai_layers"

urlpatterns = [
    path("agents/", AgentView.as_view(), name="agents_list"),
    path("agents/<slug:slug>/", AgentView.as_view(), name="agents_single"),
    path("models/", LanguageModelView.as_view(), name="models_list"),
    path(
        "system_prompt/",
        get_formatted_system_prompt,
        name="get_formatted_system_prompt",
    ),
    path("agents/create/random/", create_random_agent, name="create_random_agent"),
    # Agent task endpoints (Celery-backed AgentLoop execution)
    path("agent-task/conversation/", AgentTaskView.as_view(), name="agent_task_conversation"),
    # MCP endpoints
    path("mcp/<slug:agent_slug>/", mcp_server_handler, name="mcp_server"),
    path("mcp/<slug:agent_slug>/config/", get_mcp_config_json, name="mcp_config"),
]
