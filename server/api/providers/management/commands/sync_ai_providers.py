from django.core.management.base import BaseCommand

from api.providers.seed import sync_ai_providers


class Command(BaseCommand):
    help = (
        "Ensure known AI providers (Ollama, OpenAI, Google, Anthropic) exist in the DB. "
        "Anthropic is only created when ANTHROPIC_API_KEY is set."
    )

    def handle(self, *args, **options):
        created = sync_ai_providers()
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Created providers: {', '.join(created)}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("All expected AI providers already exist.")
            )
