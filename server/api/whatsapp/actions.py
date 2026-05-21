import json
import os
import re

import requests
from django.conf import settings
from pydantic import BaseModel, Field

from api.messaging.actions import transcribe_audio
from api.messaging.models import Conversation, Message
from api.utils.color_printer import printer
from api.utils.openai_functions import create_structured_completion

from .models import WSNumber


def _graph_token() -> str:
    return (getattr(settings, "WHATSAPP_GRAPH_API_TOKEN", None) or "").strip()


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
        "Authorization": f"Bearer {_graph_token()}",
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
        "Authorization": f"Bearer {_graph_token()}",
    }
    printer.red("Sending interactive message")
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

    response = requests.post(url, headers=headers, data=json.dumps(message_payload))

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


def send_message(
    business_phone_number_id, to, message, message_platform_id=None
) -> str | None:
    if not to or not message:
        raise ValueError("To and message fields are required.")

    url = f"https://graph.facebook.com/v21.0/{business_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {_graph_token()}",
        "Content-Type": "application/json",
    }
    data: dict = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": message[:4090]},
    }
    if message_platform_id:
        data["context"] = {"message_id": message_platform_id}

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print("Error sending message:", response.json())
        raise Exception("Failed to send message.")
    printer.success("Message sent successfully.")

    return response.json().get("messages")[0].get("id")


def verify_whatsapp_number(country_code, phone_number, method, cert, pin=None):
    url = "http://your-api-url/v1/account"  # Replace with the actual API URL

    headers = {"Content-Type": "application/json"}

    payload = {
        "cc": country_code,
        "phone_number": phone_number,
        "method": method,
        "cert": cert,
    }

    if pin:
        payload["pin"] = pin

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code in [201, 202]:
        return response.json()
    else:
        return {"error": response.status_code, "message": response.text}


def download_audio(business_phone_number_id, audio_id):
    from .media import fetch_whatsapp_media_bytes

    data, _mime = fetch_whatsapp_media_bytes(str(audio_id))
    audio_file_path = f"/tmp/{audio_id}.ogg"
    with open(audio_file_path, "wb") as audio_file:
        audio_file.write(data)
    return audio_file_path


def _strip_markdown_for_whatsapp(text: str) -> str:
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    return t.strip()


def _strip_attachment_manifest_for_whatsapp(text: str) -> str:
    """
    Remove internal attachment metadata blocks from outbound WhatsApp text.
    """
    if not text:
        return ""

    lines = text.splitlines()
    cleaned: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "Attachments available from this message:":
            i += 1
            while i < len(lines) and lines[i].strip().startswith("- "):
                i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            continue
        cleaned.append(lines[i])
        i += 1

    return "\n".join(cleaned).strip()


class ReactionPick(BaseModel):
    emoji: str = Field(
        description="Single WhatsApp-valid emoji reaction to the user's last message"
    )


def _pick_whatsapp_reaction(user_text: str, assistant_text: str) -> str:
    system = (
        "Pick exactly one short emoji suitable as a WhatsApp reaction to the user's message, "
        "given the assistant reply. Output only common reaction emojis (e.g. thumbs up, check, heart, robot). "
        "Avoid skin-tone modifiers or multi-codepoint sequences."
    )
    user = f"User:\n{user_text[:2000]}\n\nAssistant:\n{assistant_text[:2000]}"
    out = create_structured_completion(
        model="gpt-4o-mini",
        response_format=ReactionPick,
        system_prompt=system,
        user_prompt=user,
    )
    return (out.emoji or "👍")[:8]


def deliver_whatsapp_reply(
    *,
    conversation: Conversation,
    assistant_message_id: int,
    inbound_wamid: str | None,
):
    """Send assistant attachments and text to WhatsApp; store WAMIDs; optional reaction."""
    from .outbound_media import deliver_whatsapp_attachments

    ws_number = conversation.ws_number
    if not ws_number or not ws_number.platform_id:
        raise ValueError("Conversation has no WSNumber or platform_id")

    assistant = Message.objects.get(
        id=assistant_message_id, conversation=conversation, type="assistant"
    )
    user_msg = (
        Message.objects.filter(
            conversation=conversation,
            type="user",
            id__lt=assistant.id,
        )
        .order_by("-id")
        .first()
    )

    if inbound_wamid and user_msg:
        meta = dict(user_msg.metadata or {})
        meta["whatsapp_wamid"] = inbound_wamid
        user_msg.metadata = meta
        user_msg.save(update_fields=["metadata"])

    body = _strip_markdown_for_whatsapp(assistant.text or "")
    body = _strip_attachment_manifest_for_whatsapp(body)
    reply_to = conversation.whatsapp_last_inbound_wamid
    to = conversation.whatsapp_user_number
    phone_id = ws_number.platform_id

    media_wamids = deliver_whatsapp_attachments(
        phone_number_id=phone_id,
        to=to,
        assistant_message=assistant,
        reply_to_message_id=reply_to,
    )

    out_wamid: str | None = None
    if body:
        # Reply context on first outbound only: media if any, otherwise text.
        text_reply_to = reply_to if not media_wamids else None
        out_wamid = send_message(phone_id, to, body, text_reply_to)

    ameta = dict(assistant.metadata or {})
    if media_wamids:
        ameta["whatsapp_media_wamids"] = media_wamids
    if out_wamid:
        ameta["whatsapp_wamid"] = out_wamid
    assistant.metadata = ameta
    assistant.save(update_fields=["metadata"])

    if inbound_wamid and user_msg and user_msg.text:
        try:
            emoji = _pick_whatsapp_reaction(user_msg.text, body)
            send_reaction(
                ws_number.platform_id,
                conversation.whatsapp_user_number,
                inbound_wamid,
                emoji,
            )
            umeta = dict(user_msg.metadata or {})
            umeta["whatsapp_reaction"] = emoji
            user_msg.metadata = umeta
            user_msg.save(update_fields=["metadata"])
        except Exception as e:
            printer.red(f"WhatsApp reaction skipped: {e}")


def send_whatsapp_fallback_text(
    conversation: Conversation,
    *,
    inbound_wamid: str | None = None,
    text: str | None = None,
):
    ws_number = conversation.ws_number
    if not ws_number or not ws_number.platform_id or not conversation.whatsapp_user_number:
        return
    msg = text or "Sorry, something went wrong. Please try again in a moment."
    send_message(
        ws_number.platform_id,
        conversation.whatsapp_user_number,
        msg,
        inbound_wamid or conversation.whatsapp_last_inbound_wamid,
    )


def handle_interactive_message(webhook_data, message):
    printer.red("Interactive message received")


def handle_image_message(webhook_data, message):
    business_phone_number_id = webhook_data["entry"][0]["changes"][0]["value"][
        "metadata"
    ]["phone_number_id"]
    try:
        ws_number = WSNumber.objects.get(platform_id=business_phone_number_id)
    except WSNumber.DoesNotExist:
        printer.red(
            f"WSNumber with platform_id {business_phone_number_id} not found"
        )
        return

    user_phone = message["from"]
    from .conversations import get_or_create_whatsapp_conversation
    from .inbound import process_image_inbound

    conv = get_or_create_whatsapp_conversation(ws_number, user_phone)
    conv.whatsapp_last_inbound_wamid = message["id"]
    conv.save(update_fields=["whatsapp_last_inbound_wamid", "updated_at"])

    mark_message_as_read(business_phone_number_id, message["id"])

    image = message.get("image") or {}
    try:
        process_image_inbound(
            ws_number=ws_number,
            conversation=conv,
            user_phone=user_phone,
            inbound_wamid=message["id"],
            image=image if isinstance(image, dict) else {},
        )
    except Exception as e:
        printer.red(f"WhatsApp image inbound failed: {e}")


def handle_audio_message(webhook_data, message):
    audio_url = message["audio"]["id"]
    business_phone_number_id = webhook_data["entry"][0]["changes"][0]["value"][
        "metadata"
    ]["phone_number_id"]

    audio_file_path = download_audio(business_phone_number_id, audio_url)
    transcription = transcribe_audio(audio_file_path)
    printer.green("Transcription: ", transcription)

    synthetic = dict(message)
    synthetic["type"] = "text"
    synthetic["text"] = {"body": transcription}
    handle_message_received(webhook_data, synthetic)


def handle_document_message(webhook_data, message):
    business_phone_number_id = webhook_data["entry"][0]["changes"][0]["value"][
        "metadata"
    ]["phone_number_id"]
    try:
        ws_number = WSNumber.objects.get(platform_id=business_phone_number_id)
    except WSNumber.DoesNotExist:
        printer.red(
            f"WSNumber with platform_id {business_phone_number_id} not found"
        )
        return

    user_phone = message["from"]
    from .conversations import get_or_create_whatsapp_conversation
    from .inbound import process_document_inbound

    conv = get_or_create_whatsapp_conversation(ws_number, user_phone)
    conv.whatsapp_last_inbound_wamid = message["id"]
    conv.save(update_fields=["whatsapp_last_inbound_wamid", "updated_at"])

    mark_message_as_read(business_phone_number_id, message["id"])

    document = message.get("document") or {}
    try:
        process_document_inbound(
            ws_number=ws_number,
            conversation=conv,
            user_phone=user_phone,
            inbound_wamid=message["id"],
            document=document if isinstance(document, dict) else {},
        )
    except Exception as e:
        printer.red(f"WhatsApp document inbound failed: {e}")


def handle_webhook(webhook_data):
    printer.blue("Handling webhook")
    printer.green(webhook_data)
    value = (
        webhook_data.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
    )
    messages = value.get("messages") or []
    if not messages:
        return
    message = messages[0]
    if message.get("type") == "text":
        handle_message_received(webhook_data=webhook_data, message=message)
    elif message.get("type") == "audio":
        handle_audio_message(webhook_data=webhook_data, message=message)
    elif message.get("type") == "image":
        handle_image_message(webhook_data=webhook_data, message=message)
    elif message.get("type") == "document":
        handle_document_message(webhook_data=webhook_data, message=message)
    elif message.get("type") == "interactive":
        handle_interactive_message(webhook_data=webhook_data, message=message)


def handle_message_received(webhook_data, message):
    from .conversations import get_or_create_whatsapp_conversation
    from .inbound import process_text_inbound

    business_phone_number_id = webhook_data["entry"][0]["changes"][0]["value"][
        "metadata"
    ]["phone_number_id"]

    try:
        ws_number = WSNumber.objects.get(platform_id=business_phone_number_id)
    except WSNumber.DoesNotExist:
        printer.red(
            f"WSNumber with platform_id {business_phone_number_id} not found, maybe we need to create it? Why I'm receiving webhooks from it?"
        )
        return

    user_phone = message["from"]
    conv = get_or_create_whatsapp_conversation(ws_number, user_phone)
    conv.whatsapp_last_inbound_wamid = message["id"]
    conv.save(update_fields=["whatsapp_last_inbound_wamid", "updated_at"])

    mark_message_as_read(business_phone_number_id, message["id"])

    body = (message.get("text") or {}).get("body") or ""
    process_text_inbound(
        ws_number=ws_number,
        conversation=conv,
        user_phone=user_phone,
        inbound_wamid=message["id"],
        body=body,
    )


def mark_message_as_read(business_number_id, ws_message_id):
    try:
        url = f"https://graph.facebook.com/v21.0/{business_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {_graph_token()}",
            "Content-Type": "application/json",
        }
        data = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": ws_message_id,
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            printer.success(
                f"Message with ID {ws_message_id} marked as read successfully."
            )
        else:
            printer.red("Error marking message as read:", response.json())
            raise Exception("Failed to mark message as read.")

    except Exception as e:
        printer.red(f"Error marking message as read: {str(e)}")
