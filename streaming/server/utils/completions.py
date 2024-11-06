import base64
from openai import OpenAI
import anthropic
from ..logger import get_custom_logger
import fitz

logger = get_custom_logger("completions")


class TextStreamingHandler:
    client = None
    max_tokens = 4096
    attachments = []

    def __init__(
        self,
        provider: str,
        api_key: str,
        config: dict = {},
        prev_messages=[],
        agent_slug=None,
    ) -> None:
        if provider == "openai":
            self.client = OpenAI(api_key=api_key)
        elif provider == "ollama":
            self.client = OpenAI(api_key=api_key, base_url="http://localhost:11434/v1")
        elif provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=api_key)

        self.provider = provider
        self.prev_messages = prev_messages
        self.config = config
        self.agent_slug = agent_slug

    def stream(self, system: str, text: str, model: str):
        if self.provider in ["openai", "ollama"]:
            return self.stream_openai(system, text, model)
        elif self.provider == "anthropic":
            print("trying to generate with Antnrhopic")
            return self.stream_anthropic(system, text, model)

        print("PROVIDER NOT FOUND")

    def stream_openai(self, system: str, text: str, model: str):

        messages = [
            {"role": "system", "content": system},
        ]
        for m in self.prev_messages:
            if m["type"] == "user":
                messages.append({"role": "user", "content": m["text"]})
            else:
                found_version = next(
                    (
                        item
                        for item in m["versions"]
                        if item["agent_slug"] == self.agent_slug
                    ),
                    None,
                )
                if found_version:
                    messages.append(
                        {"role": "assistant", "content": found_version["text"]}
                    )

        messages.append({"role": "user", "content": text})

        if len(self.attachments) > 0:
            for a in self.attachments:
                if "image" in a["type"]:
                    logger.debug("Appending image to messages")
                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": a["content"]},
                                }
                            ],
                        },
                    )
                else:
                    if "audio" in a["type"]:
                        logger.debug("Skipping audio file")
                        continue
                        if a["content"].startswith("data:audio/"):
                            audio_data = a["content"].split(",")[1]
                        else:
                            audio_data = a["content"]

                        messages.append(
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "This is an user recording",
                                    },
                                    {
                                        "type": "input_audio",
                                        "input_audio": {
                                            "data": audio_data,
                                            "format": "wav",
                                        },
                                    },
                                ],
                            },
                        )

        response = self.client.chat.completions.create(
            model=model,
            # model="gpt-4o-audio-preview",
            max_tokens=self.config.get("max_tokens", 3000),
            messages=messages,
            # modalities=["text"],
            frequency_penalty=self.config.get("frequency_penalty", 0),
            top_p=self.config.get("top_p", 1.0),
            presence_penalty=self.config.get("presence_penalty", 0),
            temperature=self.config.get("temperature", 0.5),
            stream=True,
            stream_options={"include_usage": True},
        )
        for chunk in response:
            try:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            except Exception:
                yield chunk.usage

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

            elif "audio" in a["type"]:
                processed.append(a)
            elif "pdf" in a["type"]:
                base64_content = a["content"]
                if base64_content.startswith("data:application/pdf;base64,"):
                    base64_content = base64_content.split(",")[1]

                try:
                    binary_content = base64.b64decode(base64_content)
                except base64.binascii.Error as e:
                    logger.error("Invalid base64 content")
                    logger.error(e)
                    continue

                if not binary_content.startswith(b"%PDF"):
                    logger.error("The decoded content is not a valid PDF")
                    continue

                try:
                    pdf_data = fitz.open(stream=binary_content, filetype="pdf")
                except fitz.fitz.FileDataError as e:
                    logger.error("Failed to open the PDF document")
                    logger.error(e)
                    continue

                text = ""
                for page in pdf_data:
                    text += page.get_text()
                a["content"] = text
                # Cut to the first 50000 characters
                a["content"] = a["content"][:50000]
                processed.append(a)

        logger.debug(f"Appending {len(processed)} attachments to the chat context")
        self.attachments = processed
