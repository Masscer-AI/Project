from api.utils.openai_functions import generate_image, create_completion_openai
from .models import Agent
from api.utils.color_printer import printer


# MANDATORY_MODELS = ["llama3.2:1b", "qwen2.5:0.5b"]
MANDATORY_MODELS = ["llama3.2:1b"]


def check_models_for_providers():
    from api.utils.color_printer import printer
    from .models import LanguageModel
    from api.providers.models import AIProvider
    from api.utils.ollama_functions import list_ollama_models, pull_ollama_model

    # from api.utils.openai_functions import list_openai_models

    openai_models_objects = [
        {"name": "GPT-4", "slug": "gpt-4"},
        {"name": "Gpt 4 Turbo", "slug": "gpt-4-turbo"},
        {"name": "Gpt 4O", "slug": "gpt-4o"},
        {"name": "Gpt 4O Mini", "slug": "gpt-4o-mini"},
        {"name": "Gpt 3.5 Turbo", "slug": "gpt-3.5-turbo"},
        {"name": "ChatGPT 4O Latest", "slug": "chatgpt-4o-latest"},
        # {"name": "GPT 4O Realtime Preview", "slug": "gpt-4o-realtime-preview"},
    ]

    anthropic_models_objects = [
        {"name": "Claude 3.5 Sonnet", "slug": "claude-3-5-sonnet-20241022"},
        {"name": "Claude 3.5 Haiku", "slug": "claude-3-5-haiku-20241022"},
    ]
    # openai_models_from_api = list_openai_models()
    # printer.red(openai_models_from_api, "OPENAI MODELS FROM API")

    ollama_models = list_ollama_models()
    ollama_models = [{"name": m["name"], "slug": m["model"]} for m in ollama_models]
    ollama_models_slugs = [m["slug"] for m in ollama_models]

    should_list_again = False
    for model in MANDATORY_MODELS:
        if model not in ollama_models_slugs:
            pull_ollama_model(model)
            should_list_again = True

    if should_list_again:
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

    try:
        anthropic_provider = AIProvider.objects.get(name__iexact="anthropic")
    except AIProvider.DoesNotExist:
        printer.red("AIProvider 'anthropic' does not exist.")
        anthropic_provider = None

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

    # Create LanguageModels for Anthropic
    if anthropic_provider:
        for model in anthropic_models_objects:
            language_model, created = LanguageModel.objects.get_or_create(
                provider=anthropic_provider,
                slug=model["slug"],
                defaults={"name": model["name"]},
            )
            if created:
                printer.green(
                    f"LanguageModel '{model['name']}' created for provider 'Anthropic'."
                )

    printer.success("All models are now in the DB!")


def answer_agent_inquiry(agent_slug: str, context: str, user_message: str):
    """
    Answer an user message based on the agent configuration
    """
    agent = Agent.objects.get(slug=agent_slug)
    answer = agent.answer(context=context, user_message=user_message)
    return answer


def generate_agent_profile_picture(agent_id: int):
    """
    Generate a profile picture for the agent
    """
    printer.blue(f"Generating profile picture for agent with id {agent_id}")
    agent = Agent.objects.get(id=agent_id)
    # agent.generate_profile_picture()
    # return agent.profile_picture_url
    prompt = agent.format_prompt(context="This is a test prompt")

    _system = f"""You are an artist, designer and web developer. Your task is to provide the description of an antropomorphic representation of an AI Agent based in the system prompt of that AI Agent.
    
    This is the system prompt of the AI agent:
    ---
    {prompt}
    ---

    Based on the description above, generate a  60 words (max) description of a movie characters representing the AI agent in a frontal view to the camera in an artistical way.
    """

    prompt = create_completion_openai(
        system_prompt=_system,
        user_message="",
        model="gpt-4o-mini",
    )

    image_url = generate_image(prompt, model="dall-e-3", size="1024x1024")
    agent.profile_picture_url = image_url
    agent.save()
    printer.cyan(f"Profile picture generated for agent {agent.name}")
    return image_url
