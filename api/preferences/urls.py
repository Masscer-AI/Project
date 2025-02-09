from django.urls import path
from .views import UserPreferencesView, UserTagsView, UserVoicesView

app_name = "preferences"

urlpatterns = [
    path("", UserPreferencesView.as_view(), name="user_preferences"),
    path("tags/", UserTagsView.as_view(), name="user_tags"),
    path("voices/", UserVoicesView.as_view(), name="user_voices"),
]
