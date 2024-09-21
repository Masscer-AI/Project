import requests

API_URL = "http://127.0.0.1:8000"

def save_message(token: str, text: str, type: str, conversation: str):
    endpoint = API_URL + "/v1/messaging/messages"
    headers = {"Authorization": "Token " + token}
    body = {
        "type": type,
        "text": text,
        "conversation": conversation,
    }
    
    try:
        response = requests.post(endpoint, headers=headers, json=body)
        response.raise_for_status() 
        return response.json() 
    except requests.exceptions.RequestException as e:
        print(f"Error saving message: {e}")
        return None
