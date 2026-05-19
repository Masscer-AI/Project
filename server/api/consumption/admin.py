from django.contrib import admin

from .models import (
    Consumption,
    Currency,
    OrganizationWallet,
    OrganizationWalletTransaction,
    Wallet,
)


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ["name", "one_usd_is"]


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ["user", "balance", "unit"]


@admin.register(Consumption)
class ConsumptionAdmin(admin.ModelAdmin):
    list_display = ["user", "wallet", "amount", "is_for", "created_at"]


@admin.register(OrganizationWallet)
class OrganizationWalletAdmin(admin.ModelAdmin):
    list_display = [
        "organization",
        "subscription_balance",
        "purchased_balance",
        "total_balance_display",
        "unit",
        "updated_at",
    ]
    search_fields = ["organization__name"]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(description="Total (CU)")
    def total_balance_display(self, obj):
        return obj.total_balance


@admin.register(OrganizationWalletTransaction)
class OrganizationWalletTransactionAdmin(admin.ModelAdmin):
    list_display = ["organization", "bucket", "delta", "reason", "subscription", "created_at"]
    list_filter = ["bucket", "reason", "created_at"]
    search_fields = ["organization__name"]
    readonly_fields = ["organization", "bucket", "delta", "reason", "subscription", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
