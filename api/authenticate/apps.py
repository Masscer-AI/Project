from django.apps import AppConfig


class AuthenticateConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.authenticate"

    def ready(self):
        import api.authenticate.signals
