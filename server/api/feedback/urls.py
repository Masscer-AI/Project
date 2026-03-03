from django.urls import path
from .views import ReactionTemplateView, ReactionView

app_name = "feedback"

urlpatterns = [
    path("reaction-templates/", ReactionTemplateView.as_view(), name="reaction-templates"),
    path("reactions/", ReactionView.as_view(), name="reactions"),
]
