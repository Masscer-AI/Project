from django.apps import AppConfig


class OrgListsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.org_lists"
    label = "org_lists"
    verbose_name = "Organization lists"
