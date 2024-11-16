from django.urls import path
from .views import AgentView, get_formatted_system_prompt, create_random_agent

app_name = "ai_layers"

urlpatterns = [
    path("agents/", AgentView.as_view(), name="agents_list"),
    path("agents/<slug:slug>/", AgentView.as_view(), name="agents_single"),
    path(
        "system_prompt/",
        get_formatted_system_prompt,
        name="get_formatted_system_prompt",
    ),
    path("agents/create/random/", create_random_agent, name="create_random_agent"),
]
