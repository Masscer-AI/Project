def build_create_speech_tool_instructions() -> str:
    return (
        "\n\nSpeech generation is enabled. "
        "If the user asks for an audio version, call create_speech. "
        "Omit voice_id to use the agent or system default voice. "
        "If the user requests a specific voice, or you need to choose one, call "
        "list_voices first and pass one of its voice_id values to create_speech. "
        "output_format must be mp3 or wav. "
        "The instructions parameter controls accent, tone, speed, etc. "
        "(OpenAI voices only). "
        "When referencing the audio attachment in markdown, link it like: "
        "[Listen](attachment:<attachment_id>)."
    )
