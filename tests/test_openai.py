import os
import requests


from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def create_completion_openai(
    system_prompt: str,
    user_message: str,
    model="gpt-4o-mini",
    api_key: str = os.environ.get("OPENAI_API_KEY"),
):
    client = OpenAI(
        api_key=api_key,
    )

    completion = client.responses.create(
        model=model,
        max_output_tokens=500,
        instructions=system_prompt,
        input=user_message,
    )
    return completion.output_text


def create_completion_openai_requests(model="gpt-4o", messages=None, api_key=None):
    """
    Send a completion request to OpenAI's API.

    Args:
        model (str, optional): The OpenAI model to use. Defaults to "gpt-4o".
        messages (list, optional): List of message dictionaries. Defaults to None.
        api_key (str, optional): OpenAI API key. If None, tries to read from environment variable.

    Returns:
        dict: The response from the OpenAI API

    Raises:
        ValueError: If no API key is provided or found
        requests.RequestException: For any API request errors
    """
    # Use provided API key or try to get from environment variable
    if api_key is None:
        api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "No OpenAI API key provided. Set OPENAI_API_KEY environment variable or pass the key."
        )

    # Default to an empty list if no messages provided
    if messages is None:
        messages = [{"role": "user", "content": "Hello"}]

    # API endpoint
    url = "https://api.openai.com/v1/responses"

    # Headers
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    # Request payload
    payload = {"model": model, "input": messages}

    print(payload)
    # Make the API request
    try:
        response = requests.post(url, json=payload, headers=headers)

        # Raise an exception for bad responses
        response.raise_for_status()

        # Return the parsed JSON response
        return response.json()

    except requests.RequestException as e:
        print(f"Error making OpenAI API request: {e}")
        raise


def test_create_completion_openai():
    print("Testing create_completion_openai")
    result = create_completion_openai(
        system_prompt="You are a helpful assistant",
        user_message="What is the weather in Tokyo?",
    )

    print(result)


# test_create_completion_openai()


# Example usage
if __name__ == "__main__":
    # Example of calling the function
    response = create_completion_openai_requests(
        messages=[{"role": "user", "content": "write a haiku about ai"}]
    )

    # Extract and print the generated text
    if "output_text" in response:
        print(response["output_text"])
