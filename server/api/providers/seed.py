import os

from api.providers.models import AIProvider
from api.utils.color_printer import printer


def sync_ai_providers() -> list[str]:
    """Ensure known AI providers exist. Returns names of newly created providers."""
    created: list[str] = []

    providers_to_ensure = [
        ("ollama", "Ollama", True),
        ("openai", "OpenAI", True),
        ("google", "Google", True),
        ("anthropic", "Anthropic", bool(os.getenv("ANTHROPIC_API_KEY"))),
    ]

    for name_iexact, display_name, should_create in providers_to_ensure:
        if not should_create:
            continue
        if AIProvider.objects.filter(name__iexact=name_iexact).exists():
            continue
        AIProvider.objects.create(name=display_name)
        created.append(display_name)
        printer.green(f"AIProvider '{display_name}' created.")

    return created
