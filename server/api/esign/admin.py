from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path, reverse

from .mifiel_client import MifielAPIError, MifielClient
from .models import SignatureRequest, SignatureRequestEvent

MIFIEL_WEBHOOK_EVENT_TYPES = (
    "document_closed",
    "signer_completed",
    "signer_rejected",
    "document_deleted",
)


class SignatureRequestEventInline(admin.TabularInline):
    model = SignatureRequestEvent
    extra = 0
    fields = ("event_type", "payload", "received_at")
    readonly_fields = ("event_type", "payload", "received_at")
    can_delete = False
    ordering = ("received_at",)


@admin.register(SignatureRequest)
class SignatureRequestAdmin(admin.ModelAdmin):
    change_list_template = "admin/esign/change_list.html"

    list_display = (
        "id",
        "organization",
        "document_kind",
        "signatory_email",
        "status",
        "requested_at",
        "signed_at",
    )
    list_filter = ("status", "document_kind", "provider")
    search_fields = ("signatory_email", "signatory_name", "provider_document_id", "external_id")
    readonly_fields = (
        "id",
        "external_id",
        "provider_document_id",
        "provider_widget_id",
        "requested_at",
        "signed_at",
        "rejected_at",
        "created_at",
        "updated_at",
    )
    raw_id_fields = ("organization", "requested_by", "signatory_user", "source_file", "signed_file", "signed_file_xml")
    ordering = ("-created_at",)
    inlines = [SignatureRequestEventInline]

    def get_urls(self):
        urls = super().get_urls()
        opts = self.model._meta
        custom = [
            path(
                "register-webhooks/",
                self.admin_site.admin_view(self.register_webhooks_view),
                name=f"{opts.app_label}_{opts.model_name}_register_webhooks",
            ),
        ]
        return custom + urls

    @property
    def _changelist_url_name(self) -> str:
        opts = self.model._meta
        return f"admin:{opts.app_label}_{opts.model_name}_changelist"

    def register_webhooks_view(self, request):
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied

        webhook_path = reverse("esign:mifiel_webhook")
        webhook_url = request.build_absolute_uri(webhook_path)

        try:
            client = MifielClient()
        except MifielAPIError as e:
            self.message_user(request, str(e), level=messages.ERROR)
            return redirect(self._changelist_url_name)

        try:
            existing = {w.get("callback_type") for w in client.list_webhooks()}
        except MifielAPIError as e:
            self.message_user(
                request, f"Could not list existing Mifiel webhooks: {e}", level=messages.ERROR
            )
            return redirect(self._changelist_url_name)

        for event_type in MIFIEL_WEBHOOK_EVENT_TYPES:
            if event_type in existing:
                self.message_user(
                    request, f"'{event_type}' webhook already registered, skipped.", level=messages.INFO
                )
                continue
            try:
                client.register_webhook(url=webhook_url, callback_type=event_type)
                self.message_user(
                    request, f"Registered '{event_type}' webhook → {webhook_url}", level=messages.SUCCESS
                )
            except MifielAPIError as e:
                self.message_user(
                    request, f"Failed to register '{event_type}' webhook: {e}", level=messages.ERROR
                )

        return redirect(self._changelist_url_name)


@admin.register(SignatureRequestEvent)
class SignatureRequestEventAdmin(admin.ModelAdmin):
    list_display = ("id", "signature_request", "event_type", "received_at")
    list_filter = ("event_type",)
    readonly_fields = ("id", "signature_request", "event_type", "payload", "received_at")
    raw_id_fields = ("signature_request",)
    ordering = ("-received_at",)
