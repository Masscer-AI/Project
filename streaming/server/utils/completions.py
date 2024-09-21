from openai import OpenAI
from dotenv import load_dotenv
from ..logger import logger
import anthropic

# def create_completion(provider: str, model: str, system_prompt: str, user_message: str):
#     print("Generating completion with ", provider)

#     if provider == "openai":
#         res = create_completion_openai(system_prompt, user_message, model=model)

#     if provider == "ollama":
#         res = create_completion_ollama(system_prompt, user_message, model=model)

#     make_message_request()
#     return res


def get_system_prompt(context: str):
    SYSTEM_PROMPT = f"""
You are an useful conversational assistant. You answers must be as shorter as you can to avoid too much time while generating answers. You must keep in mind that your answer will be spoken by another AI model. Keep it simple and useful.

These are previous message between you and the user:
---
{context}
---

Continue the conversation naturally
"""
    return SYSTEM_PROMPT


class TextStreamingHandler:
    client = None
    max_tokens = 4096

    def __init__(self, provider: str, api_key: str) -> None:
        if provider == "openai":
            self.client = OpenAI(api_key=api_key)
        elif provider == "ollama":
            self.client = OpenAI(api_key=api_key, base_url="http://localhost:11434/v1")
        elif provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=api_key)

        self.provider = provider

    def stream(self, system: str, text: str, model: str):
        if self.provider in ["openai", "ollama"]:
            return self.stream_openai(system, text, model)
        elif self.provider == "anthropic":
            print("trying to generate with Antnrhopic")
            return self.stream_anthropic(system, text, model)

    def stream_openai(self, system: str, text: str, model: str):
        response = self.client.chat.completions.create(
            model=model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            temperature=0.5,
            stream=True,
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def stream_anthropic(self, system: str, text: str, model: str):
        messages = [
            {"role": "user", "content": text},
        ]

        with self.client.messages.stream(
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
            model=model,
            temperature=0.5,
        ) as stream:
            for text in stream.text_stream:
                yield text
