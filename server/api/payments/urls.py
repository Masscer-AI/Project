from django.urls import path
from .views import (
    OrganizationBillingView,
    BuyCreditsView,
    CreateCheckoutSessionView,
    CreateBillingPortalSessionView,
    ReactivateSubscriptionView,
    stripe_webhook,
)

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
        "organizations/<uuid:organization_id>/billing-portal/",
        CreateBillingPortalSessionView.as_view(),
        name="create-billing-portal-session",
    ),
    path(
        "organizations/<uuid:organization_id>/buy-credits/",
        BuyCreditsView.as_view(),
        name="buy-credits",
    ),
    path(
        "organizations/<uuid:organization_id>/subscriptions/reactivate/",
        ReactivateSubscriptionView.as_view(),
        name="reactivate-subscription",
    ),
    path(
        "webhook/",
        stripe_webhook,
        name="stripe-webhook",
    ),
]
