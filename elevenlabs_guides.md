---
title: Instant Voice Cloning quickstart
subtitle: This guide shows you how to clone a voice using the Clone Voice API.
---

This guide will show you how to create an Instant Voice Clone using the Clone Voice API. To create an Instant Voice Clone via the dashboard, refer to the [Instant Voice Clone](/docs/eleven-creative/voices/voice-cloning/instant-voice-cloning) product guide.

For an in-depth explanation of how IVC and PVC work under the hood and when to choose each, see [Voice cloning: how it works](/docs/eleven-api/concepts/voice-cloning).

## Using the Instant Voice Clone API

<Note>
  This guide assumes you have [set up your API key and SDK](/docs/eleven-api/quickstart). Complete
  the quickstart first if you haven't.
</Note>

<Steps>
    <Step title="Make the API request">
        Create a new file named `example.py` or `example.mts`, depending on your language of choice and add the following code:

        <CodeBlock>
        ```python maxLines=0
        # example.py
        import os
        from dotenv import load_dotenv
        from elevenlabs.client import ElevenLabs
        from io import BytesIO

        load_dotenv()

        elevenlabs = ElevenLabs(
          api_key=os.getenv("ELEVENLABS_API_KEY"),
        )

        voice = elevenlabs.voices.ivc.create(
            name="My Voice Clone",
            # Replace with the paths to your audio files.
            # The more files you add, the better the clone will be.
            files=[BytesIO(open("/path/to/your/audio/file.mp3", "rb").read())]
        )

        print(voice.voice_id)
        ```

        ```typescript maxLines=0
        // example.mts
        import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";
        import "dotenv/config";
        import fs from "node:fs";

        const elevenlabs = new ElevenLabsClient();

        const voice = await elevenlabs.voices.ivc.create({
            name: "My Voice Clone",
            // Replace with the paths to your audio files.
            // The more files you add, the better the clone will be.
            files: [
                fs.createReadStream(
                    "/path/to/your/audio/file.mp3",
                ),
            ],
        });

        console.log(voice.voiceId);
        ```
        </CodeBlock>
    </Step>
    <Step title="Execute the code">
        <CodeBlock>
            ```python
            python example.py
            ```

            ```typescript
            npx tsx example.mts
            ```
        </CodeBlock>

        You should see the voice ID printed to the console.
    </Step>

</Steps>

## Next steps

<CardGroup cols={2}>
  <Card
    title="Professional voice cloning"
    icon="file:assets/icons/pvc.svg"
    href="/docs/eleven-api/guides/how-to/voices/professional-voice-cloning"
  >
    Create a higher-quality clone by fine-tuning a model on your voice samples.
  </Card>
  <Card
    title="Voice cloning: how it works"
    icon="file:assets/icons/voice-cloning.svg"
    href="/docs/eleven-api/concepts/voice-cloning"
  >
    Understand the technical differences between IVC and PVC and when to choose each.
  </Card>
</CardGroup>

---

