from django.contrib import admin
from django import forms
from django.utils import timezone
from .models import (
    Token,
    PublishableToken,
    CredentialsManager,
    Organization,
    OrganizationMember,
)


class TokenAdminForm(forms.ModelForm):
    class Meta:
        model = Token
        fields = "__all__"
        # widgets = {
        #     "key": forms.HiddenInput(),
        # }


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    form = TokenAdminForm
    list_display = (
        "key",
        "user",
        "token_type",
        "expires_at",
        "created_at",
        "updated_at",
    )
    search_fields = ("key", "user__username", "token_type")
    list_filter = ("token_type", "expires_at", "created_at", "updated_at")

    def revoke_immediately(self, request, queryset):
        queryset.update(expires_at=timezone.now())

    revoke_immediately.short_description = "Revoke selected tokens immediately"

    actions = [revoke_immediately]


@admin.register(PublishableToken)
class PublishableTokenAdmin(admin.ModelAdmin):
    list_display = (
        "token",
        "created_at",
        "expires_at",
        "duration_minutes",
        "duration_hours",
        "duration_days",
    )
    search_fields = ("token",)
    list_filter = ("created_at", "expires_at")

    def revoke_immediately(self, request, queryset):
        queryset.update(expires_at=timezone.now())

    revoke_immediately.short_description = "Revoke selected tokens immediately"

    actions = [revoke_immediately]


@admin.register(CredentialsManager)
class CredentialsManagerAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "openai_api_key",
        "brave_api_key",
        "anthropic_api_key",
        "pexels_api_key",
        "elevenlabs_api_key",
        "heygen_api_key",
    )
    search_fields = (
        "organization",
        "openai_api_key",
        "brave_api_key",
        "anthropic_api_key",
        "pexels_api_key",
        "elevenlabs_api_key",
        "heygen_api_key",
    )
    list_filter = ("organization",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "owner")
    search_fields = ("name", "description", "owner")
    list_filter = ("name", "description", "owner")


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ("organization", "user")
    search_fields = ("organization", "user")
    list_filter = ("organization", "user")
