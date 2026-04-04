import logging
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

logger = logging.getLogger(__name__)

# Titles are always generated with this OpenAI model (not the chat agent's model).
TITLE_MODEL = "gpt-4.1-mini"
TITLE_MAX_OUTPUT_TOKENS = 256


def _preview_text(text: str | None, max_len: int = 200) -> str:
    if not text:
        return ""
    t = text.replace("\n", " ").strip()
    return (t[:max_len] + "…") if len(t) > max_len else t


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

    logger.info(
        "generate_conversation_title START conversation_id=%s",
        conversation_id,
    )
    try:
        c = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        logger.warning(
            "generate_conversation_title conversation not found: id=%s",
            conversation_id,
        )
        return False

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
        except Exception:
            logger.exception(
                "generate_conversation_title Agent lookup failed slug=%s",
                agent_slug,
            )

    logger.info(
        "generate_conversation_title agent resolved: conversation_id=%s agent_slug=%s "
        "agent_id=%s has_custom_title_prompt=%s",
        conversation_id,
        agent_slug,
        getattr(agent, "id", None),
        bool(agent and agent.conversation_title_prompt),
    )

    # Usar el prompt personalizado del agente si existe, sino el default
    system = agent.conversation_title_prompt if agent and agent.conversation_title_prompt else default_system
    system += "\n\nIMPORTANT: The title must be at most 50 characters long."

    messages = c.messages.order_by("created_at")[:2]
    formatted_messages = []
    for message in messages:
        role = "AI" if message.type == "assistant" else "User"
        formatted_messages.append(f"{role}: {message.text}")

    user_message = "\n".join(formatted_messages)

    msg_count = c.messages.count()
    logger.info(
        "generate_conversation_title messages: conversation_id=%s total_messages=%s "
        "snippet_for_model_messages=%d user_message_preview=%r",
        conversation_id,
        msg_count,
        len(formatted_messages),
        _preview_text(user_message, 300),
    )

    if not user_message.strip():
        logger.warning(
            "generate_conversation_title empty user_message (no text to title on): "
            "conversation_id=%s",
            conversation_id,
        )

    logger.info(
        "generate_conversation_title LLM call: conversation_id=%s model=%s",
        conversation_id,
        TITLE_MODEL,
    )

    title = None
    try:
        title = create_completion_openai(
            system,
            user_message,
            model=TITLE_MODEL,
            max_tokens=TITLE_MAX_OUTPUT_TOKENS,
            temperature=0.0,
        )
    except Exception:
        logger.exception(
            "generate_conversation_title LLM call failed: conversation_id=%s model=%s",
            conversation_id,
            TITLE_MODEL,
        )
        raise

    if not title or not str(title).strip():
        logger.warning(
            "generate_conversation_title LLM returned empty title: conversation_id=%s raw=%r",
            conversation_id,
            title,
        )

    if title and title.startswith('"') and title.endswith('"'):
        title = title[1:-1]

    # Enforce 50 character limit regardless of prompt or LLM response
    if title and len(title) > 50:
        title = title[:50].rstrip()

    c.title = title
    c.save()
    logger.info(
        "generate_conversation_title saved: conversation_id=%s title=%r",
        conversation_id,
        title,
    )
    data = {
        "title": title,
        "conversation_id": str(c.id),
    }
    route_id = None
    if c.user_id:
        route_id = c.user_id
    elif c.widget_visitor_session_id:
        route_id = f"widget_session:{c.widget_visitor_session_id}"

    if route_id is not None:
        try:
            notify_user(route_id, event_type="title_updated", data=data)
            logger.info(
                "generate_conversation_title notify_user sent: conversation_id=%s route_id=%r",
                conversation_id,
                route_id,
            )
        except Exception:
            logger.exception(
                "generate_conversation_title notify_user failed: conversation_id=%s route_id=%r",
                conversation_id,
                route_id,
            )
    else:
        logger.warning(
            "generate_conversation_title skip notify_user (no route): conversation_id=%s "
            "user_id=%s widget_visitor_session_id=%s",
            conversation_id,
            c.user_id,
            c.widget_visitor_session_id,
        )

    logger.info(
        "generate_conversation_title SUCCESS conversation_id=%s",
        conversation_id,
    )
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
    """Transcribe audio using the centralized TranscriptionService."""
    from api.utils.transcription import transcription_service

    if output_format == "vtt":
        return transcription_service.transcribe_to_vtt(audio_file_url, delete_after=True)

    return transcription_service.transcribe_to_text(audio_file_url, delete_after=True)


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
