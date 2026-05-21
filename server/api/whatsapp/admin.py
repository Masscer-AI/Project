import random

from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html

from . import graph_webhook_setup as wa_graph
from .models import WSNumber


@admin.register(WSNumber)
class WhatsAppNumberAdmin(admin.ModelAdmin):
    change_form_template = "admin/whatsapp/wsnumber/change_form.html"
    list_display = (
        "organization",
        "user",
        "number",
        "platform_id",
        "waba_id",
        "verified",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "user__username",
        "number",
        "organization__name",
        "platform_id",
        "waba_id",
    )
    list_filter = ("verified", "created_at")
    readonly_fields = ("created_at", "updated_at", "webhook_callback_preview")

    @admin.display(description="Webhook callback URL")
    def webhook_callback_preview(self, obj: WSNumber | None) -> str:
        del obj  # shown on add and change; does not depend on instance
        try:
            url = wa_graph.whatsapp_webhook_callback_url()
            return format_html(
                '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
                url,
                url,
            )
        except RuntimeError as exc:
            return format_html(
                '<span class="errors">{}</span> '
                "(set <code>API_BASE_URL</code> or <code>API_URL</code> to the public HTTPS origin of this API.)",
                str(exc),
            )

    def get_urls(self):
        urls = super().get_urls()
        info = self.opts.app_label, self.opts.model_name
        custom = [
            path(
                "<path:object_id>/register-phone/",
                self.admin_site.admin_view(self.register_phone_view),
                name="%s_%s_register_phone" % info,
            ),
            path(
                "<path:object_id>/setup-waba-webhook/",
                self.admin_site.admin_view(self.setup_waba_webhook_view),
                name="%s_%s_setup_waba_webhook" % info,
            ),
            path(
                "<path:object_id>/check-webhook-config/",
                self.admin_site.admin_view(self.check_webhook_config_view),
                name="%s_%s_check_webhook_config" % info,
            ),
        ]
        return custom + urls

    def _change_url(self, object_id: str) -> str:
        return reverse(
            "admin:%s_%s_change" % (self.opts.app_label, self.opts.model_name),
            args=[object_id],
        )

    def register_phone_view(
        self, request: HttpRequest, object_id: str
    ) -> HttpResponseRedirect:
        change_url = self._change_url(object_id)
        if request.method != "POST":
            return HttpResponseRedirect(change_url)
        ws = self.get_object(request, object_id)
        if ws is None:
            self.message_user(request, "WSNumber not found.", level=messages.ERROR)
            return HttpResponseRedirect(change_url)
        if not self.has_change_permission(request, ws):
            self.message_user(request, "Permission denied.", level=messages.ERROR)
            return HttpResponseRedirect(change_url)
        pid = (ws.platform_id or "").strip()
        if not pid:
            self.message_user(
                request,
                "platform_id (Meta phone number id) is required.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(change_url)
        pin = f"{random.randint(0, 999999):06d}"
        try:
            wa_graph.register_phone_number(pid, pin)
            self.message_user(
                request,
                f"{ws.name or ws.number}: phone number registered with Graph.",
            )
        except RuntimeError as exc:
            if wa_graph.is_already_registered_error(exc):
                self.message_user(
                    request,
                    f"{ws.name or ws.number}: already registered — no action needed. "
                    "Use 'Setup WABA & webhook' for this environment.",
                )
            else:
                self.message_user(request, str(exc), level=messages.ERROR)
        return HttpResponseRedirect(change_url)

    def setup_waba_webhook_view(
        self, request: HttpRequest, object_id: str
    ) -> HttpResponseRedirect:
        change_url = self._change_url(object_id)
        if request.method != "POST":
            return HttpResponseRedirect(change_url)
        ws = self.get_object(request, object_id)
        if ws is None:
            self.message_user(request, "WSNumber not found.", level=messages.ERROR)
            return HttpResponseRedirect(change_url)
        if not self.has_change_permission(request, ws):
            self.message_user(request, "Permission denied.", level=messages.ERROR)
            return HttpResponseRedirect(change_url)
        verify = (getattr(settings, "WHATSAPP_WEBHOOK_VERIFY_TOKEN", "") or "").strip()
        if not verify:
            self.message_user(
                request,
                "WHATSAPP_WEBHOOK_VERIFY_TOKEN is not set.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(change_url)
        try:
            callback = wa_graph.whatsapp_webhook_callback_url()
        except RuntimeError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return HttpResponseRedirect(change_url)
        try:
            waba_id = wa_graph.resolve_waba_id_for_ws_number(ws)
        except RuntimeError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return HttpResponseRedirect(change_url)
        if not waba_id:
            self.message_user(
                request,
                "Could not resolve WABA id: set waba_id on this WSNumber or fix platform_id / token.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(change_url)
        try:
            wa_graph.subscribe_waba_to_app(waba_id)
            apps = wa_graph.get_subscribed_apps(waba_id)
            app_id = wa_graph.first_subscribed_app_id(apps)
            if not app_id:
                self.message_user(
                    request,
                    "Could not read app id from subscribed_apps response.",
                    level=messages.ERROR,
                )
                return HttpResponseRedirect(change_url)
            wa_graph.subscribe_app_webhook_fields(app_id, callback, verify)
        except RuntimeError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return HttpResponseRedirect(change_url)
        if (getattr(ws, "waba_id", None) or "").strip() != waba_id:
            ws.waba_id = waba_id
            ws.save(update_fields=["waba_id", "updated_at"])
        self.message_user(
            request,
            f"{ws.name or ws.number}: WABA subscribed and webhook fields configured. Callback: {callback}",
        )
        return HttpResponseRedirect(change_url)

    def check_webhook_config_view(
        self, request: HttpRequest, object_id: str
    ) -> HttpResponseRedirect:
        change_url = self._change_url(object_id)
        if request.method != "POST":
            return HttpResponseRedirect(change_url)
        ws = self.get_object(request, object_id)
        if ws is None:
            self.message_user(request, "WSNumber not found.", level=messages.ERROR)
            return HttpResponseRedirect(change_url)
        if not self.has_change_permission(request, ws):
            self.message_user(request, "Permission denied.", level=messages.ERROR)
            return HttpResponseRedirect(change_url)
        try:
            waba_id = wa_graph.resolve_waba_id_for_ws_number(ws)
        except RuntimeError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return HttpResponseRedirect(change_url)
        if not waba_id:
            self.message_user(
                request,
                "Could not resolve WABA id: set waba_id on this WSNumber or fix platform_id / token.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(change_url)
        try:
            apps = wa_graph.get_subscribed_apps(waba_id)
            if not apps:
                self.message_user(
                    request,
                    "No apps subscribed to this WABA.",
                    level=messages.WARNING,
                )
                return HttpResponseRedirect(change_url)
            app_id = wa_graph.first_subscribed_app_id(apps)
            if not app_id:
                self.message_user(
                    request,
                    "Could not read app id from subscribed_apps response.",
                    level=messages.ERROR,
                )
                return HttpResponseRedirect(change_url)
            subscriptions = wa_graph.get_app_webhook_subscriptions(app_id)
            summary = wa_graph.format_subscription_summary(subscriptions)
            app_name = (
                (apps[0].get("whatsapp_business_api_data") or {}).get("name") or app_id
            )
            self.message_user(request, f"{app_name}: {summary}")
        except RuntimeError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
        return HttpResponseRedirect(change_url)
