import requests
import json

API_URL = "http://127.0.0.1:8000"


def save_message(message: dict, conversation: str, token: str):

    endpoint = API_URL + "/v1/messaging/messages"
    headers = {"Authorization": "Token " + token}

    body = {
        "type": message["type"],
        "text": message["text"],
        "attachments": json.dumps(message["attachments"]),
        "conversation": conversation,
    }

    try:
        response = requests.post(endpoint, headers=headers, json=body)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error saving message: {e}")
        return None


def get_results(
    query_text: str, agent_slug: str, token: str, conversation_id: str = None
):

    endpoint = API_URL + "/v1/rag/query/"
    headers = {"Authorization": "Token " + token}
    body = {
        "agent_slug": agent_slug,
        "query": query_text,
        "conversation_id": conversation_id,
    }

    try:
        response = requests.post(endpoint, headers=headers, json=body)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error saving message: {e}")
        return None


def get_system_prompt(agent_slug: str, context: str, token: str):

    endpoint = API_URL + "/v1/ai_layers/system_prompt/"
    headers = {"Authorization": "Token " + token}
    body = {
        "agent_slug": agent_slug,
        "context": context,
        # "conversation_id": conversation_id,
    }

    try:
        response = requests.post(endpoint, headers=headers, json=body)
        response.raise_for_status()
        return response.json().get("system_prompt")
    except requests.exceptions.RequestException as e:
        print(f"Error saving message: {e}")
        return None
