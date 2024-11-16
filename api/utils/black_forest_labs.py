import os
import requests
import random

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
    # Create a random integer from 1 to 100000
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
    api_key: str = os.environ.get("BFL_API_KEY"),
    output_format: str = "png",
):
    endpoint = flux_models_to_endpoint[model]
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
        },
    ).json()
    return req["id"]
