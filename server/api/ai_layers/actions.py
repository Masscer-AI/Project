from api.utils.openai_functions import (
    generate_image,
    create_completion_openai,
)
from .models import Agent
from api.utils.color_printer import printer

MANDATORY_MODELS = ["llama3.2:1b"]

def check_models_for_providers():
    from api.utils.color_printer import printer
    from .models import LanguageModel
    from api.providers.models import AIProvider
    from api.utils.ollama_functions import list_ollama_models, pull_ollama_model

    openai_models_objects = [

        {
            "name": "GPT-5 Mini",
            "slug": "gpt-5-mini",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "0.25 USD / 1000000",
                    "output": "2.00 USD / 1000000",
                }
            },
        },
        {
            "name": "GPT-5",
            "slug": "gpt-5",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "1.25 USD / 1000000",
                    "output": "10.00 USD / 1000000",
                }
            },
        },
        {
            "name": "GPT-5.5",
            "slug": "gpt-5.5",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "5.00 USD / 1000000",
                    "output": "30.00 USD / 1000000",
                }
            },
        },
        {
            "name": "GPT-5.6 Sol",
            "slug": "gpt-5.6-sol",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "5.00 USD / 1000000",
                    "output": "30.00 USD / 1000000",
                }
            },
        },
        {
            "name": "GPT-5.6 Terra",
            "slug": "gpt-5.6-terra",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "2.50 USD / 1000000",
                    "output": "15.00 USD / 1000000",
                }
            },
        },
        {
            "name": "GPT-5.6 Luna",
            "slug": "gpt-5.6-luna",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "1.00 USD / 1000000",
                    "output": "6.00 USD / 1000000",
                }
            },
        },

        {
            "name": "GPT-5.4 Nano",
            "slug": "gpt-5.4-nano",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "0.20 USD / 1000000",
                    "output": "1.25 USD / 1000000",
                }
            },
        },
        {
            "name": "GPT-5.4 Mini",
            "slug": "gpt-5.4-mini",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "0.75 USD / 1000000",
                    "output": "4.50 USD / 1000000",
                }
            },
        },
        {
            "name": "GPT-5.4",
            "slug": "gpt-5.4",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "2.50 USD / 1000000",
                    "output": "15.00 USD / 1000000",
                }
            },
        },
        {
            "name": "GPT-5.4 Pro",
            "slug": "gpt-5.4-pro",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "30.00 USD / 1000000",
                    "output": "180.00 USD / 1000000",
                }
            },
        },
    ]

    google_models_objects = [
        {
            "name": "Gemini 3.1 Flash Lite (Preview)",
            "slug": "gemini-3.1-flash-lite-preview",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "0.25 USD / 1000000",
                    "output": "1.50 USD / 1000000",
                }
            },
        },
        {
            "name": "Gemini 2.5 Flash",
            "slug": "gemini-2.5-flash",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "0.30 USD / 1000000",
                    "output": "2.50 USD / 1000000",
                }
            },
        },
        {
            "name": "Gemini 2.5 Pro",
            "slug": "gemini-2.5-pro",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "2.50 USD / 1000000",
                    "output": "15.00 USD / 1000000",
                }
            },
        },
        {
            "name": "Gemini 3.1 Pro (Preview)",
            "slug": "gemini-3.1-pro-preview",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "4.00 USD / 1000000",
                    "output": "18.00 USD / 1000000",
                }
            },
        },
        {
            "name": "Gemini 3.5 Flash",
            "slug": "gemini-3.5-flash",
            "is_reasoning_model": True,
            "pricing": {
                "text": {
                    "prompt": "1.50 USD / 1000000",
                    "output": "9.00 USD / 1000000",
                }
            },
        },
    ]

    try:
        openai_provider = AIProvider.objects.get(name__iexact="openai")
    except AIProvider.DoesNotExist:
        printer.red("AIProvider 'openai' does not exist.")
        openai_provider = None

    try:
        google_provider = AIProvider.objects.get(name__iexact="google")
    except AIProvider.DoesNotExist:
        printer.red("AIProvider 'google' does not exist.")
        google_provider = None

    if openai_provider:
        for model in openai_models_objects:
            language_model, created = LanguageModel.objects.get_or_create(
                provider=openai_provider,
                slug=model["slug"],
                defaults={
                    "name": model["name"],
                    "pricing": model["pricing"],
                    "is_reasoning_model": model.get("is_reasoning_model", False),
                },
            )

            if created:
                printer.green(
                    f"LanguageModel '{model['name']}' created for provider 'OpenAI'."
                )

            if not created:
                updated = False
                if language_model.pricing != model["pricing"]:
                    language_model.pricing = model["pricing"]
                    updated = True
                if language_model.is_reasoning_model != model.get("is_reasoning_model", False):
                    language_model.is_reasoning_model = model.get("is_reasoning_model", False)
                    updated = True
                if updated:
                    language_model.save()
                    printer.yellow(
                        f"Updated LanguageModel '{model['name']}' (OpenAI)."
                    )

    if google_provider:
        for model in google_models_objects:
            language_model, created = LanguageModel.objects.get_or_create(
                provider=google_provider,
                slug=model["slug"],
                defaults={
                    "name": model["name"],
                    "pricing": model["pricing"],
                    "is_reasoning_model": model.get("is_reasoning_model", False),
                },
            )

            if created:
                printer.green(
                    f"LanguageModel '{model['name']}' created for provider 'Google'."
                )

            if not created:
                updated = False
                if language_model.pricing != model["pricing"]:
                    language_model.pricing = model["pricing"]
                    updated = True
                if language_model.is_reasoning_model != model.get(
                    "is_reasoning_model", False
                ):
                    language_model.is_reasoning_model = model.get(
                        "is_reasoning_model", False
                    )
                    updated = True
                if updated:
                    language_model.save()
                    printer.yellow(
                        f"Updated LanguageModel '{model['name']}' (Google)."
                    )

    printer.success("All LLMs are now in the DB!")

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
