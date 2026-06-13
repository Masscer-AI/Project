from django.urls import path

from .views import (
    integrations_callback,
    integrations_connect,
    integrations_disconnect,
    integrations_list,
)

app_name = "integrations"

urlpatterns = [
    path("", integrations_list, name="list"),
    path("<str:provider>/connect/", integrations_connect, name="connect"),
    path("<str:provider>/callback/", integrations_callback, name="callback"),
    path("<str:provider>/disconnect/", integrations_disconnect, name="disconnect"),
]
