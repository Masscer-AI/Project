import os
import requests
import random
import time
from .color_printer import printer

# request = requests.post(
#     'https://api.bfl.ml/v1/flux-pro-1.1',
#     headers={
#         'accept': 'application/json',
#         'x-key': os.environ.get("BFL_API_KEY"),
#         'Content-Type': 'application/json',
#     },
#     json={
#         'prompt': 'A cat on its back legs running like a human is holding a big silver fish with its arms. The cat is running away from the shop owner and has a panicked look on his face. The scene is situated in a crowded market.',
#         'width': 1024,
#         'height': 768,
#     },
# ).json()


def create_random_seed():
    return random.randint(1, 100000)


flux_models_to_endpoint = {
    "flux-pro-1.1-ultra": "https://api.bfl.ml/v1/flux-pro-1.1-ultra",
    "flux-pro-1.1": "https://api.bfl.ml/v1/flux-pro-1.1",
    "flux-pro": "https://api.bfl.ml/v1/flux-pro",
    "flux-dev": "https://api.bfl.ml/v1/flux-dev",
}


def request_flux_generation(
    prompt: str,
    width: int,
    height: int,
    model: str = "flux-dev",
    steps: int = 40,
    seed: int = create_random_seed(),
    prompt_upsampling: bool = False,
    api_key: str = os.environ.get("BFL_API_KEY"),
):
    endpoint = flux_models_to_endpoint[model]
    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "steps": steps,
        "seed": seed,
        "prompt_upsampling": prompt_upsampling,
        "safety_tolerance": 6,
    }
    print("USING KEY", api_key)
    if model == "flux-pro-1.1-ultra":
        payload["aspect_ratio"] = f"{width}:{height}"
    try:
        req = requests.post(
            endpoint,
            headers={
                "accept": "application/json",
                "x-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
        )

        # Check if the request was successful
        req.raise_for_status()  # Raises an error for bad responses (4xx or 5xx)

        return req.json()["id"]

    except requests.exceptions.HTTPError as e:
        if req.status_code == 422:
            error_details = req.json().get("detail", [])
            print("Validation Error fields:")
            for error in error_details:
                print(f"Field: {error.get('loc')}, Message: {error.get('msg')}")
        else:
            print(f"An unexpected error occurred while generating flux image: {e}")

    return None


def get_result_url(result_id: str, api_key: str = os.environ.get("BFL_API_KEY")):
    url = f"https://api.bfl.ml/v1/get_result?id={result_id}"

    while True:
        response = requests.get(
            url,
            headers={
                "accept": "application/json",
                "x-key": api_key,
            },
        ).json()

        if response.get("status") == "Ready":
            return response["result"]["sample"]
        else:
            printer.blue(
                "Waiting to retry...", "STATUS NOT READY", response.get("status")
            )
            time.sleep(1.5)


def request_image_edit_with_mask(
    image_base64: str,
    prompt: str,
    mask_base64: str = None,
    steps: int = 50,
    prompt_upsampling: bool = False,
    guidance: int = 60,
    output_format: str = "jpeg",
    safety_tolerance: int = 2,
    api_key: str = os.environ.get("BFL_API_KEY"),
):
    url = "https://api.bfl.ml/v1/flux-pro-1.0-fill"

    payload = {
        "image": image_base64,
        "prompt": prompt,
        "steps": steps,
        "prompt_upsampling": prompt_upsampling,
        "guidance": guidance,
        "output_format": output_format,
        "safety_tolerance": safety_tolerance,
    }

    if mask_base64:
        payload["mask"] = mask_base64

    headers = {
        "Content-Type": "application/json",
        "X-Key": api_key,
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Raises an error for bad responses (4xx or 5xx)
        return response.json()["id"]

    except requests.exceptions.HTTPError as e:
        if response.status_code == 422:
            error_details = response.json().get("detail", [])
            print("Validation Error fields:")
            for error in error_details:
                print(f"Field: {error.get('loc')}, Message: {error.get('msg')}")
        else:
            print(f"An unexpected error occurred while editing the image: {e}")

    return None





def generate_with_control_image(
    prompt: str,
    control_image_base64: str,
    model: str = "flux-pro-1.0-canny",  # Default to Canny
    steps: int = 50,
    seed: int = create_random_seed(),
    prompt_upsampling: bool = False,
    guidance: int = 30,
    output_format: str = "png",
    safety_tolerance: int = 2,
    api_key: str = os.environ.get("BFL_API_KEY"),
):
    # Define the endpoint for the chosen model
    model_to_endpoint = {
        "flux-pro-1.0-canny": "https://api.bfl.ml/v1/flux-pro-1.0-canny",
        "flux-pro-1.0-depth": "https://api.bfl.ml/v1/flux-pro-1.0-depth",
    }

    if model not in model_to_endpoint:
        raise ValueError(f"Invalid model selected: {model}")

    url = model_to_endpoint[model]

    # Create the payload
    payload = {
        "prompt": prompt,
        "control_image": control_image_base64,  # Base64-encoded control image
        "steps": steps,
        "seed": seed,
        "prompt_upsampling": prompt_upsampling,
        "guidance": guidance,
        "output_format": output_format,
        "safety_tolerance": safety_tolerance,
    }

    headers = {
        "Content-Type": "application/json",
        "X-Key": api_key,
    }

    try:
        # Make the POST request to the API
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Check for HTTP errors

        # Return the task ID to fetch the generated image later
        return response.json()["id"]

    except requests.exceptions.HTTPError as e:
        if response.status_code == 422:
            error_details = response.json().get("detail", [])
            print("Validation Error fields:")
            for error in error_details:
                print(f"Field: {error.get('loc')}, Message: {error.get('msg')}")
        else:
            print(f"An unexpected error occurred while generating the image: {e}")

    return None
