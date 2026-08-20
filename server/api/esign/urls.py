from django.urls import path

from .views import mifiel_webhook

app_name = "esign"

urlpatterns = [
    path("webhook", mifiel_webhook, name="mifiel_webhook"),
]
