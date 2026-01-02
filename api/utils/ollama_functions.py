import requests
from openai import OpenAI
from api.utils.color_printer import printer


def list_ollama_models():
    url = "http://localhost:11434/api/tags"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return models
        else:
            return []
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        printer.yellow(f"Ollama is not available at {url}. Skipping model list.")
        return []
    except Exception as e:
        printer.yellow(f"Error connecting to Ollama: {e}. Skipping model list.")
        return []


def pull_ollama_model(slug, insecure=False, stream=False):
    printer.blue(f"PULLING OLLAMA MODEL {slug}")
    url = "http://localhost:11434/api/pull"
    payload = {"name": slug, "insecure": insecure, "stream": stream}

    try:
        # It's a POST request, so let's use the right method
        response = requests.post(url, json=payload, timeout=30)
        
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
            printer.yellow(f"Failed to pull model: {response.status_code} - {response.text}")
            return None
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        printer.yellow(f"Ollama is not available at {url}. Cannot pull model {slug}.")
        return None
    except Exception as e:
        printer.yellow(f"Error pulling model {slug}: {e}")
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
