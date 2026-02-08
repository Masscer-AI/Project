import os
import threading
import time

from openai import OpenAI


SUPPORTED_AUDIO_FORMATS = [
    "flac", "m4a", "mp3", "mp4", "mpeg",
    "mpga", "oga", "ogg", "wav", "webm",
]


def _delete_file_after_delay(file_path: str, delay: int = 5):
    """Delete a file after a specified delay."""
    time.sleep(delay)
    try:
        os.remove(file_path)
        print(f"File {file_path} deleted successfully.")
    except Exception as e:
        print(f"Error deleting file {file_path}: {e}")


class TranscriptionService:
    """
    Centralized transcription service using OpenAI's Whisper API.
    Supports multiple output formats: text, vtt, verbose_json, srt.
    """

    def __init__(self, model: str = "whisper-1"):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = model

    def transcribe_file(
        self,
        file_path: str,
        output_format: str = "verbose_json",
        delete_after: bool = True,
    ) -> str:
        """
        Transcribe an audio/video file using OpenAI Whisper API.

        Args:
            file_path: Path to the audio/video file.
            output_format: Response format — 'text', 'vtt', 'srt', 'verbose_json'.
            delete_after: Whether to delete the file after transcription.

        Returns:
            The transcription text (or raw VTT/SRT string depending on format).
        """
        ext = os.path.splitext(file_path)[1].lstrip(".").lower()
        if ext not in SUPPORTED_AUDIO_FORMATS:
            raise ValueError(
                f"Unsupported audio format: .{ext}. "
                f"Supported: {', '.join(SUPPORTED_AUDIO_FORMATS)}"
            )

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        try:
            with open(file_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    response_format=output_format,
                    model=self.model,
                    file=audio_file,
                )
        except Exception as e:
            print(f"Transcription error: {e}")
            raise

        if delete_after:
            threading.Thread(
                target=_delete_file_after_delay, args=(file_path,)
            ).start()

        # For 'vtt' and 'srt' formats the API returns a raw string
        if output_format in ("vtt", "srt"):
            return transcription

        # For 'verbose_json' the response is an object with .text, .language, etc.
        if output_format == "verbose_json":
            return transcription

        # For 'text' format
        return transcription

    def transcribe_to_vtt(
        self,
        file_path: str,
        delete_after: bool = True,
    ) -> str:
        """Convenience: transcribe and return VTT formatted string."""
        return self.transcribe_file(
            file_path, output_format="vtt", delete_after=delete_after
        )

    def transcribe_to_text(
        self,
        file_path: str,
        delete_after: bool = True,
    ) -> str:
        """Convenience: transcribe and return plain text."""
        result = self.transcribe_file(
            file_path, output_format="verbose_json", delete_after=delete_after
        )
        return result.text


# Module-level singleton for easy import
transcription_service = TranscriptionService()
