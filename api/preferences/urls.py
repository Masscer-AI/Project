from django.urls import path
from .views import (
    UserPreferencesView,
    UserTagsView,
    UserVoicesView,
    WebPagesView,
    WebPageDetailView,
)

app_name = "preferences"

urlpatterns = [
    path("", UserPreferencesView.as_view(), name="user_preferences"),
    path("tags/", UserTagsView.as_view(), name="user_tags"),
    path("voices/", UserVoicesView.as_view(), name="user_voices"),
    path("webpages/", WebPagesView.as_view(), name="webpages"),
    path("webpages/<int:page_id>/", WebPageDetailView.as_view(), name="webpage_detail"),
]
