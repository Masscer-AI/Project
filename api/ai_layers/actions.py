def check_models_for_providers():
    from api.utils.color_printer import printer
    from .models import LanguageModel
    from api.providers.models import AIProvider
    from api.utils.ollama_functions import list_ollama_models

    openai_models_objects = [
        {"name": "GPT-4", "slug": "gpt-4"},
        {"name": "Gpt 4 Turbo", "slug": "gpt-4-turbo"},
        {"name": "Gpt 4O", "slug": "gpt-4o"},
        {"name": "Gpt 4O Mini", "slug": "gpt-4o-mini"},
        {"name": "Gpt 3.5 Turbo", "slug": "gpt-3.5-turbo"},
    ]

    ollama_models = list_ollama_models()
    ollama_models = [{"name": m["name"], "slug": m["model"]} for m in ollama_models]

    try:
        openai_provider = AIProvider.objects.get(name__iexact="openai")
    except AIProvider.DoesNotExist:
        printer.red("AIProvider 'openai' does not exist.")
        openai_provider = None

    try:
        ollama_provider = AIProvider.objects.get(name__iexact="ollama")
    except AIProvider.DoesNotExist:
        printer.red("AIProvider 'ollama' does not exist.")
        ollama_provider = None

    # Create LanguageModels for OpenAI
    if openai_provider:
        for model in openai_models_objects:
            language_model, created = LanguageModel.objects.get_or_create(
                provider=openai_provider,
                slug=model["slug"],
                defaults={"name": model["name"]},
            )
            if created:
                printer.green(
                    f"LanguageModel '{model['name']}' created for provider 'OpenAI'."
                )
            else:
                pass
                # printer.yellow(
                #     f"LanguageModel '{model['name']}' already exists for provider 'OpenAI'."
                # )

    # Create LanguageModels for Ollama
    if ollama_provider:
        for model in ollama_models:
            language_model, created = LanguageModel.objects.get_or_create(
                provider=ollama_provider,
                slug=model["slug"],
                defaults={"name": model["name"]},
            )
            if created:
                printer.green(
                    f"LanguageModel '{model['name']}' created for provider 'Ollama'."
                )
            else:
                pass
                # printer.yellow(
                #     f"LanguageModel '{model['name']}' already exists for provider 'Ollama'."
                # )

    printer.success("All models are now in the DB!")
    