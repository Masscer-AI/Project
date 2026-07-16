from django.contrib import admin

from api.mcp_oauth.models import (
    OAuthAccessToken,
    OAuthAuthorizationCode,
    OAuthAuthorizationRequest,
    OAuthClient,
    OAuthRefreshToken,
)


@admin.register(OAuthClient)
class OAuthClientAdmin(admin.ModelAdmin):
    list_display = ("client_name", "client_id", "registration_source", "disabled", "created_at")
    list_filter = ("registration_source", "disabled")
    search_fields = ("client_name", "client_id")


@admin.register(OAuthAuthorizationRequest)
class OAuthAuthorizationRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "user", "expires_at", "created_at")
    readonly_fields = ("created_at",)


@admin.register(OAuthAuthorizationCode)
class OAuthAuthorizationCodeAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "user", "mcp_client", "consumed_at", "expires_at")


@admin.register(OAuthAccessToken)
class OAuthAccessTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "user", "mcp_client", "revoked", "expires_at")


@admin.register(OAuthRefreshToken)
class OAuthRefreshTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "user", "family_id", "revoked", "rotated_at", "expires_at")
