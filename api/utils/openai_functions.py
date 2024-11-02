from openai import OpenAI
import requests
from pydantic import BaseModel
import os
import tiktoken


def create_completion_openai(
    system_prompt: str, user_message: str, model="gpt-4o-mini"
):
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
    )

    completion = client.chat.completions.create(
        model=model,
        max_tokens=500,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {"role": "user", "content": user_message},
        ],
    )
    return completion.choices[0].message.content


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
        model=model,
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


def generate_speech_api(
    text: str,
    output_path: str,
    model: str = "tts-1",
    voice: str = "onyx",
    output_format: str = "mp3",
    api_key: str = os.environ.get("OPENAI_API_KEY"),
):
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {api_key}",
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
            audio += chunk

        print(output_path, "AUDIO WILL LIVE IN")
        with open(output_path, "wb") as audio_file:
            audio_file.write(audio)

        print(f"Audio saved to {output_path}")
        return audio

    except requests.exceptions.RequestException as e:
        print(f"An error occurred generating speech API: {e}")
        return b""


def list_openai_models():
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
    )

    return client.models.list()


def count_tokens_from_text(text: str, model: str = "gpt-4o-mini"):
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text)
    return len(tokens)
