import base64
import getpass
import os
import sys
import tempfile
from pathlib import Path

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from api.ai_layers.tools.create_image import GOOGLE_IMAGE_LOCATION, _setup_google_credentials
from api.messaging.models import MessageAttachment


IMAGE_MIME_PREFIXES = ("image/",)

GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "masscer-492023")


class Command(BaseCommand):
    help = "Interactively generate images using Gemini (Nano Banana 2 Lite)"

    def add_arguments(self, parser):
        parser.add_argument("--email", type=str, default=None, help="User email")
        parser.add_argument("--password", type=str, default=None, help="User password")

    def handle(self, *args, **kwargs):
        # --- Auth ---
        self.stdout.write(self.style.MIGRATE_HEADING("=== Gemini Image Generator ===\n"))
        email = kwargs.get("email") or input("Email: ").strip()
        password = kwargs.get("password") or getpass.getpass("Password: ")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR("No user found with that email."))
            sys.exit(1)

        authenticated = authenticate(username=user.username, password=password)
        if authenticated is None:
            self.stderr.write(self.style.ERROR("Invalid credentials."))
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS(f"Authenticated as {user.username}\n"))

        # --- Prompt ---
        self.stdout.write("Describe the image you want to generate:")
        prompt = input("> ").strip()
        if not prompt:
            self.stderr.write(self.style.ERROR("Prompt cannot be empty."))
            sys.exit(1)

        # --- Optional reference attachment ---
        reference_part = None
        use_ref = input("\nUse an existing image attachment as reference? [y/N]: ").strip().lower()

        if use_ref == "y":
            attachments = list(
                MessageAttachment.objects.filter(
                    user=user,
                    kind="file",
                ).exclude(file="").filter(
                    content_type__startswith="image/"
                ).order_by("-created_at")[:20]
            )

            if not attachments:
                self.stdout.write(self.style.WARNING("No image attachments found for your account. Skipping reference.\n"))
            else:
                self.stdout.write("\nAvailable image attachments:")
                for i, att in enumerate(attachments):
                    label = att.file.name.split("/")[-1] if att.file else str(att.id)
                    self.stdout.write(f"  [{i}] {label}  ({att.content_type})  — {att.created_at.strftime('%Y-%m-%d')}")

                choice_raw = input("\nEnter number to select (or press Enter to skip): ").strip()
                if choice_raw != "":
                    try:
                        idx = int(choice_raw)
                        chosen = attachments[idx]
                    except (ValueError, IndexError):
                        self.stderr.write(self.style.ERROR("Invalid choice. Skipping reference."))
                        chosen = None

                    if chosen is not None:
                        file_path = chosen.file.path
                        mime_type = chosen.content_type or "image/jpeg"
                        self.stdout.write(self.style.SUCCESS(f"Using reference: {file_path}\n"))
                        with open(file_path, "rb") as f:
                            image_bytes = f.read()

                        from google.genai import types as genai_types
                        reference_part = genai_types.Part.from_bytes(
                            data=image_bytes,
                            mime_type=mime_type,
                        )

        # --- Generate ---
        self.stdout.write(self.style.MIGRATE_HEADING("\nGenerating image...\n"))

        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError:
            self.stderr.write(self.style.ERROR("google-genai is not installed. Run: uv add google-genai"))
            sys.exit(1)

        tmp_creds_path = None
        try:
            tmp_creds_path = _setup_google_credentials()
            if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                self.stderr.write(
                    self.style.ERROR(
                        "Vertex AI credentials required: set GOOGLE_APPLICATION_CREDENTIALS_JSON "
                        "(minified service account JSON) or GOOGLE_APPLICATION_CREDENTIALS (path to the key file), "
                        "same as production. Optional: GOOGLE_CLOUD_PROJECT."
                    )
                )
                sys.exit(1)

            client = genai.Client(
                vertexai=True,
                project=GOOGLE_CLOUD_PROJECT,
                location=GOOGLE_IMAGE_LOCATION,
            )
            self.stdout.write(
                self.style.NOTICE(
                    "Auth: Vertex AI (GOOGLE_APPLICATION_CREDENTIALS / GOOGLE_APPLICATION_CREDENTIALS_JSON).\n"
                )
            )

            parts = []
            if reference_part is not None:
                parts.append(reference_part)
            parts.append(genai_types.Part.from_text(text=prompt))

            contents = [
                genai_types.Content(role="user", parts=parts)
            ]

            config = genai_types.GenerateContentConfig(
                temperature=1,
                top_p=0.95,
                max_output_tokens=8192,
                response_modalities=["TEXT", "IMAGE"],
                image_config=genai_types.ImageConfig(aspect_ratio="1:1"),
                safety_settings=[
                    genai_types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                    genai_types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
                ],
            )

            model = "gemini-3.1-flash-lite-image"

            output_dir = Path(os.environ.get("MEDIA_ROOT", "media")) / "generated_images"
            output_dir.mkdir(parents=True, exist_ok=True)

            image_saved = False
            image_index = 0

            for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            ):
                if not chunk.candidates:
                    continue
                for part in chunk.candidates[0].content.parts:
                    if part.text:
                        self.stdout.write(part.text, ending="")
                    elif part.inline_data and part.inline_data.data:
                        image_index += 1
                        ext = part.inline_data.mime_type.split("/")[-1] if part.inline_data.mime_type else "png"
                        filename = f"generated_{image_index}.{ext}"
                        output_path = output_dir / filename

                        image_data = part.inline_data.data
                        # data may arrive as bytes or base64 string
                        if isinstance(image_data, str):
                            image_data = base64.b64decode(image_data)

                        with open(output_path, "wb") as f:
                            f.write(image_data)

                        self.stdout.write(
                            self.style.SUCCESS(f"\nImage saved: {output_path.resolve()}")
                        )
                        image_saved = True

            self.stdout.write("")  # newline after streamed text

            if not image_saved:
                self.stdout.write(self.style.WARNING("No image was returned. The model may have only produced text."))
        finally:
            if tmp_creds_path and tmp_creds_path.startswith(tempfile.gettempdir()):
                try:
                    os.unlink(tmp_creds_path)
                except OSError:
                    pass
