from django.urls import path
from .views import (
    cloudbeds_connect,
    cloudbeds_callback,
    cloudbeds_save,
    cloudbeds_status,
    cloudbeds_disconnect,
)

app_name = "cloudbeds"

urlpatterns = [
    path("connect/", cloudbeds_connect, name="connect"),
    path("callback/", cloudbeds_callback, name="callback"),
    path("save/", cloudbeds_save, name="save"),
    path("status/", cloudbeds_status, name="status"),
    path("disconnect/", cloudbeds_disconnect, name="disconnect"),
]
