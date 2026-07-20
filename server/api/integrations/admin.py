from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib import admin, messages
from django.utils import timezone

from .models import Integration, IntegrationProvider
from .providers import IntegrationProviderError, get_provider
from .services import ensure_valid_access_token, get_google_client_id, get_google_client_secret

TEST_EVENT_SUMMARY = "Masscer Calendar integration test"


def _calendar_provider_instance():
    return get_provider(
        IntegrationProvider.GOOGLE_CALENDAR,
        client_id=get_google_client_id(),
        client_secret=get_google_client_secret(),
        redirect_uri="",
    )


def _this_week_bounds_rfc3339() -> tuple[str, str]:
    """Monday 00:00 through next Monday 00:00 in the active Django timezone."""
    now_local = timezone.localtime()
    start = now_local - timedelta(days=now_local.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return start.isoformat(), end.isoformat()


def _next_midnight_in_timezone(tz_name: str) -> tuple[str, str, str]:
    """Next midnight → one hour later in the given IANA timezone."""
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now >= midnight:
        midnight = midnight + timedelta(days=1)
    end = midnight + timedelta(hours=1)
    fmt = "%Y-%m-%dT%H:%M:%S"
    return midnight.strftime(fmt), end.strftime(fmt), tz_name


def _format_event_start(event: dict) -> str:
    start = event.get("start") or {}
    if start.get("dateTime"):
        return start["dateTime"]
    if start.get("date"):
        return f"{start['date']} (all day)"
    return "?"


def _format_event_window_message(event: dict) -> str:
    start = _format_event_start(event)
    end = event.get("end") or {}
    end_s = end.get("dateTime") or end.get("date") or "?"
    return f"{start} → {end_s}"


@admin.register(Integration)
class IntegrationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "provider",
        "owner_display",
        "account_email",
        "status",
        "is_expired",
        "updated_at",
    )
    list_filter = ("provider", "status")
    search_fields = ("account_email", "account_label", "user__email", "organization__name")
    readonly_fields = ("created_at", "updated_at")
    actions = [
        "list_files_in_linked_drive",
        "list_calendar_events_this_week",
        "list_masscer_calendar_test_events",
        "create_calendar_test_event",
    ]

    @admin.display(description="Owner")
    def owner_display(self, obj: Integration) -> str:
        return f"{obj.owner_type}: {obj.owner_label}"

    @admin.action(description="List files in linked Drive account")
    def list_files_in_linked_drive(self, request, queryset):
        drive_qs = queryset.filter(provider=IntegrationProvider.GOOGLE_DRIVE)
        skipped = queryset.exclude(provider=IntegrationProvider.GOOGLE_DRIVE).count()

        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped} non-Google-Drive integration(s).",
                level=messages.WARNING,
            )

        client_id = get_google_client_id()
        client_secret = get_google_client_secret()
        if not client_id or not client_secret:
            self.message_user(
                request,
                "GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is not configured.",
                level=messages.ERROR,
            )
            return

        provider = get_provider(
            IntegrationProvider.GOOGLE_DRIVE,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri="",
        )

        for integration in drive_qs:
            try:
                access_token = ensure_valid_access_token(integration)
                files = provider.list_files(access_token, limit=20)
            except IntegrationProviderError as exc:
                self.message_user(
                    request,
                    f"{integration}: failed to list files — {exc}",
                    level=messages.ERROR,
                )
                continue

            if not files:
                self.message_user(
                    request,
                    f"{integration}: no files found.",
                    level=messages.INFO,
                )
                continue

            lines = [f"{f.get('name')} ({f.get('id')})" for f in files[:20]]
            self.message_user(
                request,
                f"{integration} — {len(lines)} file(s):\n" + "\n".join(lines),
                level=messages.SUCCESS,
            )

    @admin.action(description="List this week's events (primary calendar)")
    def list_calendar_events_this_week(self, request, queryset):
        calendar_qs = queryset.filter(provider=IntegrationProvider.GOOGLE_CALENDAR)
        skipped = queryset.exclude(provider=IntegrationProvider.GOOGLE_CALENDAR).count()

        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped} non-Google-Calendar integration(s).",
                level=messages.WARNING,
            )

        client_id = get_google_client_id()
        client_secret = get_google_client_secret()
        if not client_id or not client_secret:
            self.message_user(
                request,
                "GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is not configured.",
                level=messages.ERROR,
            )
            return

        time_min, time_max = _this_week_bounds_rfc3339()
        provider = _calendar_provider_instance()

        for integration in calendar_qs:
            try:
                access_token = ensure_valid_access_token(integration)
                events = provider.list_events(
                    access_token,
                    calendar_id="primary",
                    time_min=time_min,
                    time_max=time_max,
                    max_results=50,
                )
            except IntegrationProviderError as exc:
                self.message_user(
                    request,
                    f"{integration}: failed to list events — {exc}",
                    level=messages.ERROR,
                )
                continue

            if not events:
                self.message_user(
                    request,
                    f"{integration}: no events this week (primary, {time_min} → {time_max}).",
                    level=messages.INFO,
                )
                continue

            lines = [
                f"{_format_event_start(e)} — {e.get('summary') or '(no title)'} [{e.get('id')}]"
                for e in events
            ]
            self.message_user(
                request,
                f"{integration} — {len(lines)} event(s) this week:\n" + "\n".join(lines),
                level=messages.SUCCESS,
            )

    @admin.action(description="Find Masscer test events on primary calendar (API search)")
    def list_masscer_calendar_test_events(self, request, queryset):
        calendar_qs = queryset.filter(provider=IntegrationProvider.GOOGLE_CALENDAR)
        skipped = queryset.exclude(provider=IntegrationProvider.GOOGLE_CALENDAR).count()
        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped} non-Google-Calendar integration(s).",
                level=messages.WARNING,
            )

        client_id = get_google_client_id()
        client_secret = get_google_client_secret()
        if not client_id or not client_secret:
            self.message_user(
                request,
                "GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is not configured.",
                level=messages.ERROR,
            )
            return

        provider = _calendar_provider_instance()
        now = timezone.now()
        time_min = now.isoformat()
        time_max = (now + timedelta(days=30)).isoformat()

        for integration in calendar_qs:
            try:
                access_token = ensure_valid_access_token(integration)
                events = provider.list_events(
                    access_token,
                    calendar_id="primary",
                    time_min=time_min,
                    time_max=time_max,
                    max_results=100,
                )
            except IntegrationProviderError as exc:
                self.message_user(
                    request,
                    f"{integration}: search failed — {exc}",
                    level=messages.ERROR,
                )
                continue

            matches = [
                e
                for e in events
                if (e.get("summary") or "").startswith(TEST_EVENT_SUMMARY)
            ]
            if not matches:
                self.message_user(
                    request,
                    f"{integration}: no upcoming «{TEST_EVENT_SUMMARY}» events in the next 30 days.",
                    level=messages.WARNING,
                )
                continue

            lines = [
                f"{_format_event_window_message(e)} — {e.get('id')} — {e.get('htmlLink') or 'no link'}"
                for e in matches
            ]
            self.message_user(
                request,
                f"{integration} — {len(matches)} test event(s):\n" + "\n".join(lines),
                level=messages.SUCCESS,
            )

    @admin.action(description="Create test event at next midnight (primary calendar)")
    def create_calendar_test_event(self, request, queryset):
        calendar_qs = queryset.filter(provider=IntegrationProvider.GOOGLE_CALENDAR)
        skipped = queryset.exclude(provider=IntegrationProvider.GOOGLE_CALENDAR).count()

        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped} non-Google-Calendar integration(s).",
                level=messages.WARNING,
            )

        client_id = get_google_client_id()
        client_secret = get_google_client_secret()
        if not client_id or not client_secret:
            self.message_user(
                request,
                "GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is not configured.",
                level=messages.ERROR,
            )
            return

        provider = _calendar_provider_instance()

        for integration in calendar_qs:
            try:
                access_token = ensure_valid_access_token(integration)
                cal_tz = provider.get_calendar_timezone(access_token, calendar_id="primary")
                start_dt, end_dt, tz_name = _next_midnight_in_timezone(cal_tz)
                event_body = {
                    "summary": TEST_EVENT_SUMMARY,
                    "description": "Created from Django admin (integrations). Safe to delete.",
                    "start": {"dateTime": start_dt, "timeZone": tz_name},
                    "end": {"dateTime": end_dt, "timeZone": tz_name},
                }
                created = provider.create_event(
                    access_token,
                    calendar_id="primary",
                    event_body=event_body,
                )
                verified = provider.get_event(
                    access_token,
                    calendar_id="primary",
                    event_id=created["id"],
                )
            except IntegrationProviderError as exc:
                self.message_user(
                    request,
                    f"{integration}: failed to create test event — {exc}",
                    level=messages.ERROR,
                )
                continue

            account = integration.account_email or integration.owner_label
            self.message_user(
                request,
                (
                    f"{integration}: created «{TEST_EVENT_SUMMARY}» "
                    f"(requested {start_dt} {tz_name}; Google: {_format_event_window_message(verified)}). "
                    f"Open the link signed in as {account}. "
                    f"id={verified.get('id')} link={verified.get('htmlLink') or 'n/a'}"
                ),
                level=messages.SUCCESS,
            )
