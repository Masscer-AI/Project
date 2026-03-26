from django.urls import path
from .views import OrganizationBillingView, BuyCreditsView, CreateCheckoutSessionView, stripe_webhook

app_name = "payments"

urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/billing/",
        OrganizationBillingView.as_view(),
        name="organization-billing",
    ),
    path(
        "organizations/<uuid:organization_id>/checkout/",
        CreateCheckoutSessionView.as_view(),
        name="create-checkout-session",
    ),
    path(
        "organizations/<uuid:organization_id>/buy-credits/",
        BuyCreditsView.as_view(),
        name="buy-credits",
    ),
    path(
        "webhook/",
        stripe_webhook,
        name="stripe-webhook",
    ),
]
