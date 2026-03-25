from django.contrib import admin
from .models import WinningRates, SubscriptionPlan, Subscription, SubscriptionPayment


@admin.register(WinningRates)
class WinningRatesAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "llm_interaction_rate",
        "image_generation_rate",
        "video_generation_rate",
        "speech_synthesis_rate",
        "transcription_rate",
        "document_generation_usd",
    ]


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ["slug", "display_name", "monthly_price_usd", "credits_limit_usd", "duration_days", "is_configurable"]
    search_fields = ["slug", "display_name"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["id", "organization", "plan", "status", "payment_method", "start_date", "end_date", "is_active"]
    list_filter = ["status", "payment_method", "plan"]
    search_fields = ["organization__name", "stripe_subscription_id", "stripe_customer_id"]
    readonly_fields = ["id", "created_at", "updated_at"]

    def is_active(self, obj):
        return obj.is_active()
    is_active.boolean = True


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "subscription", "amount_usd", "method", "status", "created_at"]
    list_filter = ["status", "method"]
    search_fields = ["subscription__organization__name", "stripe_payment_intent_id"]
    readonly_fields = ["id", "created_at", "updated_at"]
