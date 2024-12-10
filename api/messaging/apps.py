from django.apps import AppConfig


class MessagingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.messaging"

    def ready(self):
        import api.messaging.signals
