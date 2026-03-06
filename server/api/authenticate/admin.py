from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django import forms
from django.utils import timezone
from django.utils.html import format_html
import pytz
from .models import (
    Token,
    PublishableToken,
    CredentialsManager,
    Organization,
    FeatureFlag,
    FeatureFlagAssignment,
    UserProfile,
    Role,
    RoleAssignment,
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


class LogoFileWidget(forms.ClearableFileInput):
    template_name = 'admin/widgets/clearable_file_input_simple.html'
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('attrs', {})
        kwargs['attrs']['accept'] = 'image/*'
        super().__init__(*args, **kwargs)


class OrganizationAdminForm(forms.ModelForm):
    timezone = forms.ChoiceField(
        choices=[(tz, tz) for tz in pytz.all_timezones],
        initial='UTC',
        help_text="Selecciona la zona horaria para mostrar los timestamps de esta organización"
    )
    
    class Meta:
        model = Organization
        fields = '__all__'
        widgets = {
            'logo': LogoFileWidget()
        }


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    form = OrganizationAdminForm
    list_display = ("name", "description", "owner", "timezone", "logo_preview")
    search_fields = ("name", "description", "owner__username")
    list_filter = ("timezone", "owner")
    readonly_fields = ("logo_preview",)
    
    fieldsets = (
        ('Información básica', {
            'fields': ('name', 'description', 'owner', 'timezone')
        }),
        ('Logo', {
            'fields': ('logo', 'logo_preview'),
            'description': 'Sube un logo para la organización.'
        }),
    )
    
    class Media:
        css = {
            'all': ('admin/css/organization_logo.css',)
        }
        js = ('admin/js/organization_logo.js',)
    
    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px;" />', obj.logo.url)
        return "Sin logo"
    logo_preview.short_description = "Logo"


class OrganizationFeatureFlagInline(admin.TabularInline):
    model = FeatureFlagAssignment
    extra = 1
    verbose_name = "Organization Assignment"
    verbose_name_plural = "Organization-Level Assignments"
    fields = ("organization", "enabled")
    autocomplete_fields = ("organization",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(user__isnull=True, organization__isnull=False)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["required"] = False
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class UserFeatureFlagInline(admin.TabularInline):
    model = FeatureFlagAssignment
    extra = 1
    verbose_name = "User Assignment"
    verbose_name_plural = "User-Level Assignments"
    fields = ("user", "enabled")
    raw_id_fields = ("user",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(user__isnull=False, organization__isnull=True)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "organization":
            kwargs["required"] = False
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("name", "created", "modified")
    search_fields = ("name",)
    list_filter = ("created", "modified")
    inlines = [OrganizationFeatureFlagInline, UserFeatureFlagInline]


@admin.register(FeatureFlagAssignment)
class FeatureFlagAssignmentAdmin(admin.ModelAdmin):
    list_display = ("feature_flag", "organization", "user", "enabled", "created", "modified")
    search_fields = ("feature_flag__name", "organization__name", "user__email", "user__username")
    list_filter = ("enabled", "created", "modified", "feature_flag")


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = "Profile"
    verbose_name_plural = "Profile"
    fields = (
        "name",
        "organization",
        "is_active",
        "avatar_url",
        "bio",
        "sex",
        "age",
        "birthday",
    )


# Extend the default User admin to include the profile inline
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = (
        "username",
        "email",
        "get_organization",
        "get_is_active_member",
        "is_staff",
        "date_joined",
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "profile__is_active",
        "profile__organization",
    )

    @admin.display(description="Organization", ordering="profile__organization__name")
    def get_organization(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.organization if profile else None

    @admin.display(description="Active member", boolean=True)
    def get_is_active_member(self, obj):
        profile = getattr(obj, "profile", None)
        if not profile or not profile.organization:
            return None
        return profile.is_active


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "enabled", "created_at", "updated_at")
    search_fields = ("name", "organization__name", "description")
    list_filter = ("enabled", "organization", "created_at", "updated_at")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "organization", "from_date", "to_date", "is_active_display", "created_at")
    search_fields = ("user__username", "user__email", "role__name", "organization__name")
    list_filter = ("organization", "role", "from_date", "to_date", "created_at", "updated_at")
    readonly_fields = ("id", "created_at", "updated_at")
    date_hierarchy = "from_date"
    
    def is_active_display(self, obj):
        """Display if the role assignment is currently active"""
        return obj.is_active()
    is_active_display.boolean = True
    is_active_display.short_description = "Active"