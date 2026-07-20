from django.urls import path

from .calendar_views import (
    google_calendar_event_detail,
    google_calendar_events_collection,
    google_calendar_list_calendars,
)
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
    path(
        "google_calendar/calendars/",
        google_calendar_list_calendars,
        name="google_calendar_calendars",
    ),
    path(
        "google_calendar/events/",
        google_calendar_events_collection,
        name="google_calendar_events",
    ),
    path(
        "google_calendar/events/<str:event_id>/",
        google_calendar_event_detail,
        name="google_calendar_event_detail",
    ),
]
