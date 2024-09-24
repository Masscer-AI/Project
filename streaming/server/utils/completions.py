from openai import OpenAI
import base64
import anthropic
import fitz
from ..logger import get_custom_logger

logger = get_custom_logger("completions")
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
    attachments = []

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
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ]

        if len(self.attachments) > 0:
            for a in self.attachments:
                if "image" in a["type"]:
                    logger.debug("Appending image to messages")
                    messages.append(
                        {"role": "user","content": [
                            {"type": "image_url", "image_url": {"url": a["content"]}}
                        ]},
                    )
                else:
                    logger.debug(f"Attaching document {a["name"]}" )
                    messages.append(
                        {"role": "user", "content": f"The following if the content of a document called: {a["name"]} and of type {a["type"]}: \n{a["content"]}"},
                    )

        response = self.client.chat.completions.create(
            model=model,
            max_tokens=self.max_tokens,
            messages=messages,
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

    def process_attachments(self, attachments=[]):
        logger.debug(f"Processing {len(attachments)} attachments")
        processed = []

        for a in attachments:
            if "image" in a["type"]:
                processed.append(a)
            elif "pdf" in a["type"]:
                base64_content = a["content"]
                if base64_content.startswith("data:application/pdf;base64,"):
                    base64_content = base64_content.split(",")[1]

                try:
                    binary_content = base64.b64decode(base64_content)
                except base64.binascii.Error as e:
                    logger.error("Invalid base64 content")
                    continue

                if not binary_content.startswith(b"%PDF"):
                    logger.error("The decoded content is not a valid PDF")
                    continue

                try:
                    pdf_data = fitz.open(stream=binary_content, filetype="pdf")
                except fitz.fitz.FileDataError as e:
                    logger.error("Failed to open the PDF document")
                    continue

                text = ""
                for page in pdf_data:
                    text += page.get_text()
                a["content"] = text
                processed.append(a)
        self.attachments = processed
