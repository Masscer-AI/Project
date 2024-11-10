import os
import requests
from .models import Conversation
from openai import OpenAI
from dotenv import load_dotenv
from django.core.files.uploadedfile import InMemoryUploadedFile
import io
from pydub import AudioSegment

from api.utils.ollama_functions import create_completion_ollama

load_dotenv()


def generate_conversation_title(conversation_id: str):
    system = """
    Given some conversation messages, please generate a title related to the conversation. The title must have an emoji at the beginning.

    The title must be a plain string without double quotes and the start or end.


    These are examples of titles with emojis at the beginning:
    💬 Conversation about Jupyter Notebooks
    📝 Notes about the meeting with Maria
    🎥 Video call analysis from recording
    💻 Code review for the new OpenAI API
    🙏🏻 User Support for John in Python

    Return ONLY the new conversation title with the emoji at the beginning.
    """
    c = Conversation.objects.get(id=conversation_id)

    messages = c.messages.order_by("created_at")[:2]
    formatted_messages = []
    for message in messages:
        role = "AI" if message.type == "assistant" else "User"
        formatted_messages.append(f"{role}: {message.text}")

    user_message = "\n".join(formatted_messages)

    title = create_completion_ollama(
        system,
        user_message,
        model="llama3.2:1b",
        max_tokens=20,
    )

    if title.startswith('"') and title.endswith('"'):
        title = title[1:-1]

    c.title = title
    c.save()
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
