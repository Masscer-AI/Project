import os
import requests
from openai import OpenAI
from dotenv import load_dotenv
from ..logger import get_custom_logger
from .completions import TextStreamingHandler
from pydantic import BaseModel

logger = get_custom_logger("openai_functions")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


def transcribe_audio(audio_file, output_format="verbose_json") -> str:
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    transcription = client.audio.transcriptions.create(
        response_format=output_format, model="whisper-1", file=audio_file
    )

    if output_format == "vtt":
        return transcription
    return transcription.text


async def stream_completion(prompt, user_message, model, attachments=[], config={}):
    logger.debug(f"MODEL TO COMPLETE: {model}")
    _provider = model["provider"].lower()
    if _provider == "openai":
        streamer = TextStreamingHandler(provider="openai", api_key=OPENAI_API_KEY, config=config)

    elif _provider == "ollama":
        streamer = TextStreamingHandler(provider="ollama", api_key="ANTHROPIC_API_KEY", config=config)

    elif _provider == "anthropic":
        streamer = TextStreamingHandler(provider="anthropic", api_key=ANTHROPIC_API_KEY, config=config)

    model_slug = model["slug"]

    content = user_message

    streamer.process_attachments(attachments)
   
    for chunk in streamer.stream(
        system=prompt,
        text=content,
        model=model_slug,
    ):
        if isinstance(chunk, str):
            yield chunk


async def generate_speech_stream(
    text: str,
    output_path: str,
    model: str = "tts-1",
    voice: str = "alloy",
    output_format: str = "mp3",
):
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    logger.debug("trying to generate speech in generate speech function")
    try:
        with open(output_path, "wb") as output_file:
            response = client.audio.speech.create(model=model, voice=voice, input=text)
            response.stream_to_file(output_file.name)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


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
            yield chunk
            audio += chunk

        with open(output_path, "wb") as audio_file:
            audio_file.write(audio)

        print(f"Audio saved to {output_path}")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return b""


def generate_image(
    prompt: str,
    model: str = "dall-e-3",
    size: str = "1024x1024",
    quality: str = "standard",
    n: int = 1,
) -> str:
    try:
        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )

        response = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
            n=n,
        )
        image_url = response.data[0].url
        return image_url
    except Exception as e:
        print(e)
        raise Exception("Your prompt doesn't satisfy OpenAI policy, sorry :(")


class ExampleStructure(BaseModel):
    salute: str


def create_structured_completion(
    model="gpt-4o",
    system_prompt: str = "You are an userful assistant",
    user_prompt: str = "",
    response_format=ExampleStructure,
    api_key: str = os.environ.get("OPENAI_API_KEY"),
):
    client = OpenAI(api_key=api_key)

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        response_format=response_format,
    )
    return completion.choices[0].message.parsed
