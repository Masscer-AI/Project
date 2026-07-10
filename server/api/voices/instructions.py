def build_create_speech_tool_instructions() -> str:
    return (
        "\n\nSpeech generation is enabled. "
        "If the user asks for an audio version, call create_speech. "
        "Omit voice_id to use the agent or system default voice. "
        "If the user requests a specific voice, or you need to choose one, call "
        "list_voices with target='speech' first and pass one of its voice_id values "
        "to create_speech. "
        "output_format must be mp3 or wav. "
        "The instructions parameter controls accent, tone, speed, etc. "
        "(OpenAI voices only). "
        "When referencing the audio attachment in markdown, link it like: "
        "[Listen](attachment:<attachment_id>)."
    )


def build_generate_dialogue_tool_instructions() -> str:
    return (
        "\n\nDialogue generation is enabled. "
        "When the user asks for a scripted conversation, scene, podcast exchange, or "
        "other multi-speaker audio, call generate_dialogue rather than create_speech. "
        "Call list_voices with target='dialogue' before selecting voices; dialogue only "
        "supports ElevenLabs voices. Use one ordered turn per speaker. "
        "Use instructions for a delivery tag at the start of a turn, or include Eleven v3 "
        "audio tags such as [whispering], [laughing], or [gentle footsteps] in the text. "
        "Keep all turn text including tags at or below 2,000 characters. "
        "When referencing the audio attachment in markdown, link it like: "
        "[Listen](attachment:<attachment_id>)."
    )
