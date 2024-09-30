from django.urls import path
from .views import AgentView

app_name = "ai_layers"

urlpatterns = [
    path("agents/", AgentView.as_view(), name="agents_list"),
]
