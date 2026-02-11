from openai import OpenAI
import requests
from pydantic import BaseModel
import os
import tiktoken
import json




def pricing_calculator(model: str, tokens: int):
    return 0


def _extract_output_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text.strip()

    chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", "") in ("output_text", "text"):
                text = getattr(content, "text", "")
                if text:
                    chunks.append(text)
    return "".join(chunks).strip()


def _response_text_format_from_pydantic(response_format):
    schema = (
        response_format.model_json_schema()
        if hasattr(response_format, "model_json_schema")
        else response_format.schema()
    )
    return {
        "type": "json_schema",
        "name": response_format.__name__,
        "schema": schema,
        "strict": True,
    }


def _extract_json_from_text(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty response received for structured output")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        if "```" in raw:
            for part in raw.split("```"):
                candidate = part.replace("json", "", 1).strip()
                if not candidate:
                    continue
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
        raise


def create_completion_openai(
    system_prompt: str,
    user_message: str,
    model="gpt-4o-mini",
    api_key: str = os.environ.get("OPENAI_API_KEY"),
    max_tokens: int = 500,
    temperature: float | None = None,
):
    client = OpenAI(
        api_key=api_key,
    )
    kwargs = {
        "model": model,
        "max_output_tokens": max_tokens,
        "instructions": system_prompt,
        "input": user_message,
    }
    is_reasoning_model = model.startswith("gpt-5") or model.startswith("o")
    if temperature is not None and not is_reasoning_model:
        kwargs["temperature"] = temperature
    completion = client.responses.create(**kwargs)
    return _extract_output_text(completion)


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

    completion = client.responses.create(
        model=model,
        instructions=system_prompt,
        input=user_prompt,
        text={"format": _response_text_format_from_pydantic(response_format)},
    )
    parsed_dict = _extract_json_from_text(_extract_output_text(completion))
    if hasattr(response_format, "model_validate"):
        return response_format.model_validate(parsed_dict)
    return response_format.parse_obj(parsed_dict)


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


def generate_image(
    prompt: str,
    model: str = "dall-e-3",
    size: str = "1024x1024",
    quality: str = "standard",
    n: int = 1,
    api_key: str = os.environ.get("OPENAI_API_KEY"),
) -> str:
    try:
        client = OpenAI(
            api_key=api_key,
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
