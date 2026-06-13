from django.contrib import admin, messages

from .models import Integration, IntegrationProvider
from .providers import IntegrationProviderError, get_provider
from .services import ensure_valid_access_token, get_google_client_id, get_google_client_secret


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
    actions = ["list_files_in_linked_drive"]

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
