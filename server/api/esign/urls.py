from django.urls import path

from .views import PublicSignatureRequestView, mifiel_webhook

app_name = "esign"

urlpatterns = [
    path("webhook", mifiel_webhook, name="mifiel_webhook"),
    path(
        "sign/<uuid:signature_request_id>/",
        PublicSignatureRequestView.as_view(),
        name="public_signature_request",
    ),
]
