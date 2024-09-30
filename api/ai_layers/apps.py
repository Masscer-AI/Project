from django.apps import AppConfig


class AiLayersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.ai_layers'
    def ready(self) -> None:
        import api.ai_layers.signals
