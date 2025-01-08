import time
import os
from runwayml import RunwayML
from typing import Literal


# Create a new image-to-video task using the "gen3a_turbo" model
def image_to_video(
    prompt_image_b64,
    prompt_text,
    api_key=os.getenv("RUNWAY_API_KEY"),
    ratio: Literal[
        "1280:768",
        "768:1280",
    ] = "768:1280",
):
    if not api_key:
        raise ValueError("RUNWAY_API_KEY is not set in the environment variables")
    client = RunwayML(api_key=api_key)
    print(prompt_text, "PROMPT TEXT")
    task = client.image_to_video.create(
        model="gen3a_turbo",
        prompt_image=prompt_image_b64,
        prompt_text=prompt_text,
        duration=5,
        ratio=ratio,
    )
    task_id = task.id

    # Poll the task until it's complete
    time.sleep(10)  # Wait for a second before polling
    task = client.tasks.retrieve(task_id)
    while task.status not in ["SUCCEEDED", "FAILED"]:
        print("Waiting for task to complete...")
        time.sleep(10)  # Wait for a second before polling
        task = client.tasks.retrieve(task_id)

    return task
