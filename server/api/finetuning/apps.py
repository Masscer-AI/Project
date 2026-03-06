from django.apps import AppConfig


class FinetuningConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.finetuning"

    def ready(self):
        import api.finetuning.signals
