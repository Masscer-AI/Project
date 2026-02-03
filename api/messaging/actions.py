import os
import requests
from .models import Conversation
from openai import OpenAI
from dotenv import load_dotenv
from django.core.files.uploadedfile import InMemoryUploadedFile
import io
from pydub import AudioSegment
from api.notify.actions import notify_user
from api.utils.ollama_functions import create_completion_ollama
from api.utils.openai_functions import create_completion_openai

load_dotenv()

# Max tokens for title generation (short string)
TITLE_MAX_TOKENS = 50


def generate_conversation_title(conversation_id: str):
    # Prompt por defecto
    default_system = """
    Given some conversation messages, please generate a title related to the conversation. The title must have an emoji at the beginning.

    The title must be a plain string without double quotes and the start or end.


    These are examples of titles with emojis at the beginning:
    💬 Conversation about Jupyter Notebooks
    📝 Notes about the meeting with Maria
    🎥 Video call analysis from recording
    💻 Code review for the new OpenAI API
    🙏🏻 User Support for John in Python

    Return ONLY the new conversation title with the emoji at the beginning. Both are mandatory, emoji + text. But up to 50 characters are allowed.
    """
    
    c = Conversation.objects.get(id=conversation_id)
    
    # Obtener el agente usado en la conversación
    agent = None
    agent_slug = None
    
    # Buscar el primer mensaje assistant para obtener el agente
    first_assistant_message = c.messages.filter(type="assistant").first()
    if first_assistant_message:
        # Intentar obtener el agent_slug de versions
        if first_assistant_message.versions and len(first_assistant_message.versions) > 0:
            agent_slug = first_assistant_message.versions[0].get("agent_slug")
        
        # Si no está en versions, intentar en agents
        if not agent_slug and first_assistant_message.agents:
            if isinstance(first_assistant_message.agents, list) and len(first_assistant_message.agents) > 0:
                agent_slug = first_assistant_message.agents[0].get("slug")
    
    # Si encontramos un agent_slug, obtener el agente
    if agent_slug:
        try:
            from api.ai_layers.models import Agent
            agent = Agent.objects.filter(slug=agent_slug).first()
        except Exception as e:
            print(f"Error getting agent: {e}")
    
    # Usar el prompt personalizado del agente si existe, sino el default
    system = agent.conversation_title_prompt if agent and agent.conversation_title_prompt else default_system

    messages = c.messages.order_by("created_at")[:2]
    formatted_messages = []
    for message in messages:
        role = "AI" if message.type == "assistant" else "User"
        formatted_messages.append(f"{role}: {message.text}")

    user_message = "\n".join(formatted_messages)

    # Use agent's LLM configuration when available; otherwise default to OpenAI
    provider = (agent.model_provider or "openai").lower() if agent else "openai"
    model_slug = (agent.llm.slug if agent and agent.llm else (agent.model_slug if agent else "gpt-4o-mini")) or "gpt-4o-mini"
    max_tokens = min(agent.max_tokens or 4000, TITLE_MAX_TOKENS) if agent else TITLE_MAX_TOKENS

    if provider == "openai":
        title = create_completion_openai(
            system,
            user_message,
            model=model_slug,
            max_tokens=max_tokens,
            temperature=agent.temperature if agent else None,
        )
    elif provider == "ollama":
        title = create_completion_ollama(
            system,
            user_message,
            model=model_slug,
            max_tokens=max_tokens,
        )
    else:
        # anthropic or unknown: fallback to OpenAI (no sync Anthropic completion in api/)
        title = create_completion_openai(
            system,
            user_message,
            model="gpt-4o-mini",
            max_tokens=max_tokens,
        )

    if title and title.startswith('"') and title.endswith('"'):
        title = title[1:-1]

    c.title = title
    c.save()
    data = {
        "title": title,
        "conversation_id": str(c.id),
    }
    notify_user(c.user.id, event_type="title_updated", data=data)
    return True


def convert_to_audio_file(
    django_file: InMemoryUploadedFile, output_format: str = "wav"
) -> io.BytesIO:
    # Load the audio file using pydub
    audio = AudioSegment.from_file(django_file)

    # Create a BytesIO object to hold the converted audio
    audio_io = io.BytesIO()

    # Export the audio in the desired format
    audio.export(audio_io, format=output_format)

    # Seek to the beginning of the BytesIO object
    audio_io.seek(0)

    return audio_io


def transcribe_audio(audio_file_url, output_format="verbose_json") -> str:
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
    )

    # Verificar el formato del archivo
    supported_formats = [
        "flac",
        "m4a",
        "mp3",
        "mp4",
        "mpeg",
        "mpga",
        "oga",
        "ogg",
        "wav",
        "webm",
    ]

    # Check if the file format is supported
    if not any(audio_file_url.endswith(ext) for ext in supported_formats):
        raise ValueError("Unsupported audio file format.")

    try:
        # Open the audio file from the given path
        with open(audio_file_url, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                response_format=output_format, model="whisper-1", file=audio_file
            )
        # Delete the file after successful transcription
        os.remove(audio_file_url)
    except Exception as e:
        print(f"An error occurred trascribing audio: {e}")
        raise

    if output_format == "vtt":
        return transcription
    return transcription.text


def generate_speech_api(
    text: str,
    output_path: str,
    model: str = "tts-1",
    voice: str = "onyx",
    output_format: str = "mp3",
):
    try:
        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            },
            json={
                "model": model,
                "input": text,
                "voice": voice,
            },
            stream=True,
        )

        response.raise_for_status()

        audio = b""
        for chunk in response.iter_content(chunk_size=2097152):
            audio += chunk  # Accumulate audio data

        print(output_path, "AUDIO WILL LIVE IN")
        with open(output_path, "wb") as audio_file:
            audio_file.write(audio)

        print(f"Audio saved to {output_path}")
        return audio  # Return the audio bytes

    except requests.exceptions.RequestException as e:
        print(f"An error occurred generaeting speech: {e}")
        return b""


def complete_message(text: str):
    system = """
    The following is the content of a textarea representing a user message.
    Please complete the message with a suggestion for the next message so the user can continue writing easily.

    COMPLETE THE FOLLOWING PART OF THE MESSAGE.
    """
    return create_completion_ollama(system, text, model="llama3.2:1b", max_tokens=20)
