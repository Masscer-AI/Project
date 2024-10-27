import os
import requests
import json
from .models import WSMessage, WSNumber, WSConversation
from django.core.exceptions import ValidationError
from api.ai_layers.actions import answer_agent_inquiry
from api.utils.color_printer import printer
from api.messaging.actions import transcribe_audio, generate_speech_api
from pydantic import BaseModel, Field
from api.utils.openai_functions import create_structured_completion
from api.utils.color_printer import printer


def send_reaction(business_phone_number_id, to, message_id, emoji):
    """
    Send a reaction to a WhatsApp user message.

    :param business_phone_number_id: The WhatsApp Business Phone Number ID
    :param to: The recipient's WhatsApp phone number
    :param message_id: The ID of the message to react to
    :param emoji: The emoji to apply as a reaction
    """
    url = f"https://graph.facebook.com/v18.0/{business_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {os.getenv('WHATSAPP_GRAPH_API_TOKEN')}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "reaction",
        "reaction": {
            "message_id": message_id,
            "emoji": emoji,
        },
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print("Error sending reaction:", response.json())
        raise Exception("Failed to send reaction.")

    printer.success(f"Reaction {emoji} sent successfully.")


def mark_message_as_read(business_phone_number_id, message_id):
    url = f"https://graph.facebook.com/v18.0/{business_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {os.getenv('GRAPH_API_TOKEN')}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print("Error marking message as read:", response.json())


def send_interactive_message(
    whatsapp_business_phone_number_id,
    user_phone_number,
    header_text,
    body_text,
    footer_text,
    buttons,
):
    url = (
        f"https://graph.facebook.com/v21.0/{whatsapp_business_phone_number_id}/messages"
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('WHATSAPP_GRAPH_API_TOKEN')}",
    }
    printer.red("Sending interactive message")
    # Construct the message payload
    message_payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": user_phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {"type": "text", "text": header_text},
            "body": {"text": body_text},
            "footer": {"text": footer_text},
            "action": {"buttons": buttons},
        },
    }

    # Send the POST request
    response = requests.post(url, headers=headers, data=json.dumps(message_payload))

    # Check the response
    if response.status_code == 200:
        printer.success("Interactive message sent successfully!")

        try:
            return response.json()["messages"][0]["id"]
        except KeyError:
            printer.red("No message id found in the response")
            return None
    else:
        print(f"Failed to send message: {response.status_code}, {response.text}")
        return None


def send_message(business_phone_number_id, to, message, message_platform_id):
    if not to or not message:
        raise ValueError("To and message fields are required.")

    url = f"https://graph.facebook.com/v21.0/{business_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {os.getenv('WHATSAPP_GRAPH_API_TOKEN')}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": message},
        "context": {"message_id": message_platform_id},
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print("Error sending message:", response.json())
        raise Exception("Failed to send message.")
    printer.success("Message sent successfully.")


def verify_whatsapp_number(country_code, phone_number, method, cert, pin=None):
    """
    Verifies a WhatsApp number using the local installations API.

    Parameters:
    - country_code (str): The numeric country code of the phone number.
    - phone_number (str): The phone number to register (without country code).
    - method (str): The method to receive the registration code ('sms' or 'voice').
    - cert (str): The Base64 encoded certificate for validation.
    - pin (str, optional): The current 6-digit PIN if two-step verification is enabled.

    Returns:
    - dict: The response from the API.
    """

    url = "http://your-api-url/v1/account"  # Replace with the actual API URL

    headers = {"Content-Type": "application/json"}

    # Prepare the request payload
    payload = {
        "cc": country_code,
        "phone_number": phone_number,
        "method": method,
        "cert": cert,
    }

    if pin:
        payload["pin"] = pin

    # Send the POST request
    response = requests.post(url, json=payload, headers=headers)

    # Check if the request was successful
    if response.status_code in [201, 202]:
        return response.json()
    else:
        return {"error": response.status_code, "message": response.text}


def save_ws_message(
    conversation,
    content,
    message_type,
    reaction=None,
    collected_info=None,
    message_platform_id=None,
):
    """
    Save a WSMessage associated with a WSConversation.

    :param conversation: WSConversation object
    :param content: The content of the message
    :param message_type: The type of message ('USER' or 'ASSISTANT')
    :return: WSMessage instance or raises ValidationError if the message cannot be saved
    """

    # Validate the message type
    if message_type not in dict(WSMessage.MESSAGE_TYPE_CHOICES):
        raise ValueError("Invalid message type. Choose either 'USER' or 'ASSISTANT'.")

    message = WSMessage(
        conversation=conversation,
        content=content,
        message_type=message_type,
        reaction=reaction,
        collected_info=collected_info,
        message_platform_id=message_platform_id,
    )

    try:
        message.save()
    except ValidationError as e:
        raise ValidationError(f"Error saving message: {e}")

    return message


def download_audio(business_phone_number_id, audio_id):
    url = f"https://graph.facebook.com/v18.0/{business_phone_number_id}/messages/{audio_id}?access_token={os.getenv('WHATSAPP_GRAPH_API_TOKEN')}"
    response = requests.get(url)

    if response.status_code != 200:
        print("Error downloading audio:", response.json())
        raise Exception("Failed to download audio.")

    # Save the audio file to a temporary path
    audio_file_path = f"/tmp/{audio_id}.ogg"
    with open(audio_file_path, "wb") as audio_file:
        audio_file.write(response.content)

    return audio_file_path


def handle_transcription(webhook_data, transcription, message):
    business_phone_number_id = webhook_data["entry"][0]["changes"][0]["value"][
        "metadata"
    ]["phone_number_id"]

    ws_number = WSNumber.objects.get(platform_id=business_phone_number_id)

    conversation, created = WSConversation.objects.get_or_create(
        user_number=message["from"],
        ai_number=ws_number,
        defaults={
            "status": "ACTIVE",
        },
    )

    context = ""
    if created:
        context = "This is the first message from the user"
    else:
        context = conversation.get_context()

    # Save the transcription as a message
    save_ws_message(
        conversation=conversation,
        content=transcription,
        message_type="USER",
    )

    ai_response = answer_agent_inquiry(
        agent_slug=ws_number.agent.slug,
        context=context,
        user_message=transcription,
    )

    send_message(business_phone_number_id, message["from"], ai_response, message["id"])
    save_ws_message(
        conversation=conversation, content=ai_response, message_type="ASSISTANT"
    )


def handle_interactive_message(webhook_data, message):
    printer.red("Interactive message received")


def handle_audio_message(webhook_data, message):
    audio_url = message["audio"]["id"]  # Get the audio file ID
    business_phone_number_id = webhook_data["entry"][0]["changes"][0]["value"][
        "metadata"
    ]["phone_number_id"]

    # Download the audio file
    audio_file_path = download_audio(business_phone_number_id, audio_url)

    # Transcribe the audio using Whisper
    transcription = transcribe_audio(audio_file_path)

    printer.green("Transcription: ", transcription)
    # Handle the transcription like a normal message
    handle_transcription(webhook_data, transcription, message)


def handle_webhook(webhook_data):
    printer.blue("Handling webhook")
    printer.green(webhook_data)
    message = (
        webhook_data.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("messages", [{}])[0]
    )
    if message.get("type") == "text":
        handle_message_received(webhook_data=webhook_data, message=message)

    elif message.get("type") == "audio":
        printer.blue("Audio message received and handling correctly")

    elif message.get("type") == "interactive":
        handle_interactive_message(webhook_data=webhook_data, message=message)
        # handle_audio_message(webhook_data=webhook_data, message=message)


class UserInfo(BaseModel):
    name: str = Field(description="The name of the user")
    language: str = Field(description="The language of the user")
    requirements: str = Field(description="The requirements of the user")


class WhatsappResponse(BaseModel):
    response: str = Field(description="The response from the AI")
    reaction: str = Field(description="The emoji to react with to the user message")
    user_info: UserInfo = Field(
        description="The user info you can collect from the message"
    )


def handle_message_received(webhook_data, message):
    business_phone_number_id = webhook_data["entry"][0]["changes"][0]["value"][
        "metadata"
    ]["phone_number_id"]

    ws_number = WSNumber.objects.get(platform_id=business_phone_number_id)

    conversation, created = WSConversation.objects.get_or_create(
        user_number=message["from"],
        ai_number=ws_number,
        defaults={
            "status": "ACTIVE",
        },
    )

    context = ""
    if created:
        context = "This is the first message from the user"
    else:
        context = conversation.get_context()

    # HACER QUE PAREAca que estoy escribiendo
    save_ws_message(
        conversation=conversation,
        content=message["text"]["body"],
        message_type="USER",
        message_platform_id=message["id"],
    )
    whatsapp_response = ws_number.agent.answer(
        context=context,
        user_message=message["text"]["body"],
        response_format=WhatsappResponse,
    )

    send_message(
        business_phone_number_id,
        message["from"],
        whatsapp_response.response,
        message["id"],
    )
    save_ws_message(
        conversation=conversation,
        content=whatsapp_response.response,
        message_type="ASSISTANT",
        reaction=whatsapp_response.reaction,
        collected_info=json.dumps(whatsapp_response.user_info.model_dump()),
    )

    send_reaction(
        webhook_data["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"],
        message["from"],
        message["id"],
        whatsapp_response.reaction,
    )

    conversation.update_user_info()


# def generate_conversation_context(conversation):
#     context = ""
#     for message in conversation.messages.all():
#         context += f"{message.message_type}: {message.content}\n"
#     return context


class ConversationContext(BaseModel):
    title: str = Field(description="The title of the conversation")
    summary: str = Field(description="The summary of the conversation")
    sentiment: str = Field(description="The sentiment of the conversation")


def generate_conversation_context(id: int):
    """
    Generate the context of a conversation by answering a message with an empty message
    """
    ws_conversation = WSConversation.objects.get(id=id)
    conversation_context = create_structured_completion(
        model="gpt-4o-mini",
        response_format=ConversationContext,
        system_prompt="You are a helpful assistant that generates conversation context",
        user_prompt=ws_conversation.get_context(),
    )
    ws_conversation.title = conversation_context.title
    ws_conversation.summary = conversation_context.summary
    ws_conversation.sentiment = conversation_context.sentiment
    ws_conversation.save()
