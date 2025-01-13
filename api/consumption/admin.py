from django.contrib import admin
from .models import Currency, Wallet, Consumption


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ["name", "one_usd_is"]


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ["user", "balance", "unit"]


@admin.register(Consumption)
class ConsumptionAdmin(admin.ModelAdmin):
    list_display = ["user", "amount", "is_for", "created_at"]


# Register your models here.
