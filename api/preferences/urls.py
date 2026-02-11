from django.urls import path
from .views import (
    UserPreferencesView,
    UserVoicesView,
    WebPagesView,
    WebPageDetailView,
)

app_name = "preferences"

urlpatterns = [
    path("", UserPreferencesView.as_view(), name="user_preferences"),
    path("voices/", UserVoicesView.as_view(), name="user_voices"),
    path("webpages/", WebPagesView.as_view(), name="webpages"),
    path("webpages/<int:page_id>/", WebPageDetailView.as_view(), name="webpage_detail"),
]
