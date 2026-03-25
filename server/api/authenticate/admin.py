from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django import forms
from django.utils import timezone
from django.utils.html import format_html
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
import calendar
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

    @property
    def inlines(self):
        from api.consumption.models import OrganizationWallet
        from api.payments.models import Subscription
        OrganizationWalletInline.model = OrganizationWallet
        SubscriptionInline.model = Subscription
        return [OrganizationWalletInline, SubscriptionInline]

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

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "subscription/<uuid:subscription_id>/renew/",
                self.admin_site.admin_view(self._renew_subscription),
                name="subscription-renew",
            ),
            path(
                "subscription/<uuid:subscription_id>/expire/",
                self.admin_site.admin_view(self._expire_subscription),
                name="subscription-expire",
            ),
        ]
        return custom + urls

    def _renew_subscription(self, request, subscription_id):
        from api.payments.models import Subscription
        from api.consumption.models import OrganizationWallet, Currency
        from decimal import Decimal
        try:
            sub = Subscription.objects.select_related("plan", "organization").get(pk=subscription_id)
            now = timezone.now()
            base = sub.end_date if sub.end_date and sub.end_date > now else now
            # Advance exactly one month (same day, handle month-end edge cases)
            month = base.month + 1 if base.month < 12 else 1
            year = base.year if base.month < 12 else base.year + 1
            day = min(base.day, calendar.monthrange(year, month)[1])
            sub.end_date = base.replace(year=year, month=month, day=day)
            sub.status = "active"
            sub.renewed_at = now
            sub.save(update_fields=["end_date", "status", "renewed_at", "updated_at"])

            # Recharge the wallet
            credits_usd = sub.get_effective_credits_limit_usd()
            if credits_usd:
                currency = Currency.objects.filter(name="Compute Unit").first()
                if currency:
                    compute_units = Decimal(credits_usd) * Decimal(currency.one_usd_is)
                    wallet = OrganizationWallet.objects.filter(organization=sub.organization).first()
                    if wallet:
                        wallet.recharge(compute_units)

            messages.success(request, f"Subscription renewed until {sub.end_date.strftime('%Y-%m-%d')}.")
        except Exception as e:
            messages.error(request, f"Could not renew subscription: {e}")

        org_id = sub.organization_id if 'sub' in dir() else None
        return HttpResponseRedirect(
            reverse("admin:authenticate_organization_change", args=[org_id]) if org_id
            else reverse("admin:authenticate_organization_changelist")
        )

    def _expire_subscription(self, request, subscription_id):
        from api.payments.models import Subscription
        try:
            sub = Subscription.objects.select_related("organization").get(pk=subscription_id)
            sub.status = "expired"
            sub.end_date = timezone.now()
            sub.save(update_fields=["status", "end_date", "updated_at"])
            messages.success(request, "Subscription expired.")
        except Exception as e:
            messages.error(request, f"Could not expire subscription: {e}")

        org_id = sub.organization_id if 'sub' in dir() else None
        return HttpResponseRedirect(
            reverse("admin:authenticate_organization_change", args=[org_id]) if org_id
            else reverse("admin:authenticate_organization_changelist")
        )


class OrganizationWalletInline(admin.TabularInline):
    model = None  # set below after import
    verbose_name = "Wallet"
    verbose_name_plural = "Wallet"
    extra = 0
    max_num = 1
    readonly_fields = ("balance_display", "unit", "updated_at")
    fields = ("balance_display", "unit", "updated_at")
    can_delete = False

    def balance_display(self, obj):
        if not obj.pk:
            return "—"
        usd = float(obj.balance) / float(obj.unit.one_usd_is) if obj.unit else 0
        return format_html(
            "<strong>${:.4f} USD</strong> &nbsp;<small style='color:#888'>{} {} · 1 USD = {} {}</small>",
            usd,
            f"{float(obj.balance):,.8f}",
            obj.unit.name if obj.unit else "",
            obj.unit.one_usd_is if obj.unit else "",
            obj.unit.name if obj.unit else "",
        )
    balance_display.short_description = "Balance"

    def has_add_permission(self, request, obj=None):
        return False


class SubscriptionInline(admin.StackedInline):
    model = None  # set below after import
    verbose_name = "Subscription"
    verbose_name_plural = "Subscription"
    extra = 0
    max_num = 1
    readonly_fields = ("id", "start_date", "created_at", "updated_at", "subscription_actions")
    fields = (
        "plan",
        "status",
        "payment_method",
        "start_date",
        "end_date",
        "credits_limit_usd",
        "stripe_subscription_id",
        "stripe_customer_id",
        "subscription_actions",
    )

    def subscription_actions(self, obj):
        if not obj.pk:
            return "—"
        renew_url = reverse("admin:subscription-renew", args=[obj.pk])
        expire_url = reverse("admin:subscription-expire", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" style="background:#417690;color:#fff;padding:4px 10px;border-radius:4px;text-decoration:none;margin-right:8px;">↻ Renew</a>'
            '<a class="button" href="{}" style="background:#ba2121;color:#fff;padding:4px 10px;border-radius:4px;text-decoration:none;" '
            'onclick="return confirm(\'Expire this subscription now?\')">✕ Expire now</a>',
            renew_url,
            expire_url,
        )
    subscription_actions.short_description = "Actions"

    def has_add_permission(self, request, obj=None):
        return False


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