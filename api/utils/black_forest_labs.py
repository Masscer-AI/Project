import os
import requests
import random
import time


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

    try:
        req = requests.post(
            endpoint,
            headers={
                "accept": "application/json",
                "x-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "prompt": prompt,
                "width": width,
                "height": height,
                "steps": steps,
                "seed": seed,
                "prompt_upsampling": prompt_upsampling,
            },
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
            print("Status not ready, waiting to retry...")
            time.sleep(1.5)
