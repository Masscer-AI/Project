from django.urls import path
from .views import UserPreferencesView

app_name = "preferences"

urlpatterns = [
    path("", UserPreferencesView.as_view(), name="user_preferences"),
]
