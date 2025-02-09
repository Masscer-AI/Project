import os
from elevenlabs.client import ElevenLabs
from elevenlabs import save


def generate_audio_elevenlabs(
    text, voice, api_key=os.getenv("ELEVENLABS_API_KEY"), filename="audio.mp3"
):
    client = ElevenLabs(api_key=api_key)

    audio = client.text_to_speech.convert(
        text=text,
        voice_id=voice,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )

    save(audio, filename)

    return filename
