from django.urls import path

from .drive_views import google_drive_import, google_drive_list_files
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
    path(
        "google_drive/files/",
        google_drive_list_files,
        name="google_drive_files",
    ),
    path(
        "google_drive/import/",
        google_drive_import,
        name="google_drive_import",
    ),
]
