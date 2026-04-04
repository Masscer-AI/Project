from openai import OpenAI
import requests
from pydantic import BaseModel
import os
import tiktoken
import json




def pricing_calculator(model: str, tokens: int):
    return 0


def _text_from_content_part(part: object) -> str | None:
    """Normalize a single content block from the Responses API to plain text."""
    if part is None:
        return None
    if isinstance(part, dict):
        typ = part.get("type")
        txt = part.get("text")
        if isinstance(txt, str) and txt.strip():
            if typ in ("output_text", "text", "refusal", None):
                return txt.strip()
            # Unknown assistant content types may still carry plain text
            if typ not in ("input_text", "reasoning"):
                return txt.strip()
        return None
    typ = getattr(part, "type", None)
    txt = getattr(part, "text", None)
    if isinstance(txt, str) and txt.strip():
        if typ in ("output_text", "text", "refusal", None):
            return txt.strip()
    return None


def _iter_output_content_items(response) -> list:
    """Flatten content parts from response.output (handles message vs flat shapes)."""
    out = []
    raw_output = getattr(response, "output", None) or []
    for item in raw_output:
        if hasattr(item, "model_dump"):
            item = item.model_dump(mode="python")
        if isinstance(item, dict):
            if item.get("type") == "reasoning":
                continue
            for c in item.get("content") or []:
                out.append(c)
        else:
            if getattr(item, "type", None) == "reasoning":
                continue
            for c in getattr(item, "content", []) or []:
                out.append(c)
    return out


def _extract_output_text_from_dump(d: dict) -> str:
    """Parse a Responses API object serialized via model_dump (shape drift tolerant)."""
    parts: list[str] = []
    for item in d.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "reasoning":
            continue
        # Some responses put assistant text directly on the output item
        if item.get("type") in ("output_text", "text") and isinstance(item.get("text"), str):
            t = item.get("text", "").strip()
            if t:
                parts.append(t)
                continue
        contents = item.get("content")
        if not isinstance(contents, list):
            continue
        for c in contents:
            t = _text_from_content_part(c)
            if t:
                parts.append(t)
    return "".join(parts).strip()


def _extract_output_text(response) -> str:
    if response is None:
        return ""

    # Aggregated helper on the SDK Response object (may be empty on some SDK/API combos)
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    # Prefer model_dump when available — matches server-side JSON shape
    if hasattr(response, "model_dump"):
        try:
            dumped = response.model_dump(mode="python")
            from_dump = _extract_output_text_from_dump(dumped)
            if from_dump:
                return from_dump
        except Exception:
            pass

    # Object graph: iterate flattened content items
    chunks: list[str] = []
    for part in _iter_output_content_items(response):
        t = _text_from_content_part(part)
        if t:
            chunks.append(t)
    text = "".join(chunks).strip()
    if text:
        return text

    # Last pass: legacy per-item iteration (older SDKs)
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", "") in ("output_text", "text"):
                raw = getattr(content, "text", "")
                if isinstance(raw, str) and raw:
                    chunks.append(raw)
    return "".join(chunks).strip()


def _fix_schema_for_openai_strict(schema: dict) -> dict:
    """Recursively patch a JSON schema so it passes OpenAI strict-mode validation.

    Two things OpenAI requires that Pydantic doesn't emit by default:
    1. Every object must have "additionalProperties": false
    2. Every object must list ALL property keys in "required"
    """
    if not isinstance(schema, dict):
        return schema

    if schema.get("type") == "object" or "properties" in schema:
        schema["additionalProperties"] = False
        props = schema.get("properties")
        if isinstance(props, dict) and props:
            schema["required"] = list(props.keys())

    for key in ("properties", "$defs", "definitions"):
        container = schema.get(key)
        if isinstance(container, dict):
            for v in container.values():
                _fix_schema_for_openai_strict(v)

    for key in ("items", "anyOf", "oneOf", "allOf"):
        value = schema.get(key)
        if isinstance(value, dict):
            _fix_schema_for_openai_strict(value)
        elif isinstance(value, list):
            for item in value:
                _fix_schema_for_openai_strict(item)

    return schema


def _response_text_format_from_pydantic(response_format):
    schema = (
        response_format.model_json_schema()
        if hasattr(response_format, "model_json_schema")
        else response_format.schema()
    )
    _fix_schema_for_openai_strict(schema)
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
