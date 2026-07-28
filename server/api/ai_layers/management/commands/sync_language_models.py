from django.core.management.base import BaseCommand

from api.ai_layers.actions import check_models_for_providers


class Command(BaseCommand):
    help = (
        "Ensure LanguageModel rows exist for known providers. "
        "Creates missing models and updates pricing/flags when definitions change. "
        "Requires AI providers to exist first (run sync_ai_providers)."
    )

    def handle(self, *args, **options):
        check_models_for_providers()
        self.stdout.write(self.style.SUCCESS("Language models synced."))
