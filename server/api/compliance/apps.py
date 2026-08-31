from django.apps import AppConfig


class ComplianceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.compliance"
    label = "compliance"
    verbose_name = "Compliance"
