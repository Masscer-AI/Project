from django.urls import path
from .views import OrganizationBillingView

app_name = "payments"

urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/billing/",
        OrganizationBillingView.as_view(),
        name="organization-billing",
    ),
]
