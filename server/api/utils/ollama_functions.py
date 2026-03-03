import requests
from openai import OpenAI
from api.utils.color_printer import printer


def list_ollama_models():
    url = "http://localhost:11434/api/tags"
    response = requests.get(url)

    if response.status_code == 200:
        models = response.json().get("models", [])
        return models
    else:
        return []


def pull_ollama_model(slug, insecure=False, stream=False):
    printer.blue(f"PULLING OLLAMA MODEL {slug}")
    url = "http://localhost:11434/api/pull"
    payload = {"name": slug, "insecure": insecure, "stream": stream}

    # It's a POST request, so let's use the right method
    response = requests.post(url, json=payload)

    if response.status_code == 200:
        printer.success("OLLAMA MODEL PULLED SUCCESSFULLY")
        if stream:
            # When streaming, we might get multiple responses
            for line in response.iter_lines():
                if line:
                    print(line.decode("utf-8"))
        else:
            # If not streaming, just return the whole response
            return response.json()
    else:
        print(f"Failed to pull model: {response.status_code} - {response.text}")
        return None


def create_completion_ollama(
    system_prompt, user_message, model="llama3.2:1b", max_tokens=1000
):
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="llama3")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content
