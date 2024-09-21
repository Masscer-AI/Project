import os
from openai import OpenAI
from dotenv import load_dotenv
import requests
import asyncio
from ..logger import logger
import anthropic
from .completions import TextStreamingHandler

# from pydub import AudioSegment
# Obtener la clave de la API desde una variable de entorno
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


# def create_completion_openai(
#     system_prompt: str, user_message: str, model="gpt-4o-mini"
# ):
#     client = OpenAI(
#         api_key=os.environ.get("OPENAI_API_KEY"),
#     )

#     completion = client.chat.completions.create(
#         model=model,
#         max_tokens=500,
#         messages=[
#             {
#                 "role": "system",
#                 "content": system_prompt,
#             },
#             {"role": "user", "content": user_message},
#         ],
#     )
#     return completion.choices[0].message.content


async def stream_completion(prompt, user_message, model, imageB64=""):
    logger.debug(f"MODEL TO COMPLETE: {model}")

    if model["provider"] == "openai":
        streamer = TextStreamingHandler(provider="openai", api_key=OPENAI_API_KEY)

    elif model["provider"] == "ollama":
        streamer = TextStreamingHandler(provider="ollama", api_key="ANTHROPIC_API_KEY")

    elif model["provider"] == "anthropic":
        streamer = TextStreamingHandler(provider="anthropic", api_key=ANTHROPIC_API_KEY)

    model_slug = model["name"]

    content = user_message

    # if imageB64 != "" and imageB64 is not None:
    #     if model_slug not in [
    #         "gpt-4-vision-preview",
    #         "gpt-4",
    #         "gpt-4o",
    #         "gpt-4-turbo",
    #         "gpt=4o-mini",
    #     ]:
    #         model_slug = "gpt-4o"
    #     logger.info(f"Image detected, using {model} model")

    #     content = [
    #         {"type": "text", "text": user_message},
    #         {"type": "image_url", "image_url": {"url": imageB64}},
    #     ]
    # TODO: Adapt to work with anthropic also
    # messages[0]["content"] = [
    #     {"type": "text", "text": user_message},
    #     {"type": "image", "source": {"type": "base64", "data": imageB64}}
    # ]

    # max_tokens = 4000
    # if model == "gpt-4o-mini":
    #     max_tokens = 10000

    # response = client.chat.completions.create(
    #     model=model_slug,
    #     max_tokens=max_tokens,
    #     messages=[
    #         {"role": "system", "content": prompt},
    #         {"role": "user", "content": content},
    #     ],
    #     temperature=0.5,
    #     stream=True,
    # )

    # for chunk in response:
    #     if chunk.choices[0].delta.content:
    #         yield chunk.choices[0].delta.content

    for chunk in streamer.stream(
        system=prompt, text=content, model=model_slug
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

    try:
        with open(output_path, "wb") as output_file:
            response = client.audio.speech.create(model=model, voice=voice, input=text)
            response.stream_to_file(output_file.name)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def generate_speech_api(
    text: str, model: str = "tts-1-1106", voice: str = "onyx"
) -> bytes:
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
        )

        response.raise_for_status()

        audio = b""
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            audio += chunk

        return audio

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
