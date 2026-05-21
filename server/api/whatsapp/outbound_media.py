"""Send agent-generated MessageAttachment files to WhatsApp (Graph API)."""

from __future__ import annotations

import logging
import mimetypes
from typing import Any

import requests
from django.conf import settings

from api.messaging.attachment_urls import absolute_file_url_for_attachment
from api.messaging.models import Message, MessageAttachment

logger = logging.getLogger(__name__)

_GRAPH_API_BASE = "https://graph.facebook.com/v21.0"

# WhatsApp Cloud API size limits (bytes).
_MAX_BYTES: dict[str, int] = {
    "image": 5 * 1024 * 1024,
    "audio": 16 * 1024 * 1024,
    "video": 16 * 1024 * 1024,
    "document": 100 * 1024 * 1024,
}


def _graph_token() -> str:
    token = (getattr(settings, "WHATSAPP_GRAPH_API_TOKEN", None) or "").strip()
    if not token:
        raise RuntimeError("WHATSAPP_GRAPH_API_TOKEN is not configured")
    return token


def whatsapp_media_type_for_attachment(att: MessageAttachment) -> str | None:
    """
    Map attachment to WhatsApp message type: image | audio | video | document.
    Returns None if the file cannot be sent as outbound media.
    """
    if att.kind != "file" or not att.file:
        return None
    ctype = (att.content_type or "").lower().split(";")[0].strip()
    if not ctype:
        guessed, _ = mimetypes.guess_type(att.file.name or "")
        ctype = (guessed or "").lower()
    if ctype.startswith("image/"):
        return "image"
    if ctype.startswith("audio/"):
        return "audio"
    if ctype.startswith("video/"):
        return "video"
    # Documents: docx, pdf, etc.
    if ctype or att.file.name:
        return "document"
    return None


def _filename_for_attachment(att: MessageAttachment, wa_type: str) -> str:
    name = (att.file.name or "").split("/")[-1] if att.file else ""
    if name:
        return name[:240]
    ext = {
        "image": ".png",
        "audio": ".mp3",
        "video": ".mp4",
        "document": ".bin",
    }.get(wa_type, ".bin")
    return f"file{ext}"


def read_attachment_file_bytes(att: MessageAttachment) -> tuple[bytes, str, str]:
    """Return (bytes, mime_type, filename)."""
    if not att.file:
        raise ValueError("Attachment has no file")
    filename = _filename_for_attachment(att, whatsapp_media_type_for_attachment(att) or "document")
    ctype = (att.content_type or "").split(";")[0].strip()
    if not ctype:
        guessed, _ = mimetypes.guess_type(filename)
        ctype = guessed or "application/octet-stream"
    with att.file.open("rb") as fh:
        data = fh.read()
    return data, ctype, filename


def upload_whatsapp_media(
    phone_number_id: str,
    *,
    file_bytes: bytes,
    mime_type: str,
    wa_type: str,
    filename: str,
) -> str:
    """Upload bytes to Graph /media; returns media id."""
    url = f"{_GRAPH_API_BASE}/{phone_number_id}/media"
    headers = {"Authorization": f"Bearer {_graph_token()}"}
    files = {"file": (filename, file_bytes, mime_type)}
    data = {"messaging_product": "whatsapp", "type": wa_type}
    response = requests.post(url, headers=headers, data=data, files=files, timeout=120)
    if response.status_code != 200:
        raise RuntimeError(f"WhatsApp media upload failed: {response.status_code} {response.text}")
    media_id = (response.json() or {}).get("id")
    if not media_id:
        raise ValueError("WhatsApp media upload returned no id")
    return str(media_id)


def send_whatsapp_media_message(
    phone_number_id: str,
    to: str,
    wa_type: str,
    *,
    link: str | None = None,
    media_id: str | None = None,
    caption: str | None = None,
    filename: str | None = None,
    reply_to_message_id: str | None = None,
) -> str | None:
    """Send image/audio/video/document. Returns outbound WAMID."""
    if not link and not media_id:
        raise ValueError("link or media_id is required")
    if wa_type not in {"image", "audio", "video", "document"}:
        raise ValueError(f"Unsupported WhatsApp media type: {wa_type}")

    media_obj: dict[str, Any] = {}
    if media_id:
        media_obj["id"] = media_id
    else:
        media_obj["link"] = link

    if caption and wa_type in {"image", "video", "document"}:
        media_obj["caption"] = caption[:1024]
    if filename and wa_type == "document":
        media_obj["filename"] = filename[:240]

    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": wa_type,
        wa_type: media_obj,
    }
    if reply_to_message_id:
        payload["context"] = {"message_id": reply_to_message_id}

    url = f"{_GRAPH_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {_graph_token()}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(
            f"WhatsApp media message failed: {response.status_code} {response.text}"
        )
    messages = (response.json() or {}).get("messages") or []
    if not messages:
        return None
    return messages[0].get("id")


def send_attachment_to_whatsapp(
    phone_number_id: str,
    to: str,
    att: MessageAttachment,
    *,
    reply_to_message_id: str | None = None,
    caption: str | None = None,
) -> str | None:
    """
    Send one MessageAttachment. Prefers public HTTPS link; falls back to upload.
    """
    wa_type = whatsapp_media_type_for_attachment(att)
    if not wa_type:
        logger.warning(
            "Skipping WhatsApp outbound media: unsupported attachment id=%s kind=%s",
            att.id,
            att.kind,
        )
        return None

    file_bytes, mime_type, filename = read_attachment_file_bytes(att)
    max_size = _MAX_BYTES.get(wa_type, _MAX_BYTES["document"])
    if len(file_bytes) > max_size:
        raise ValueError(
            f"Attachment too large for WhatsApp {wa_type} ({len(file_bytes)} bytes, max {max_size})"
        )

    public_url = absolute_file_url_for_attachment(att)
    if public_url and public_url.startswith("https://"):
        try:
            return send_whatsapp_media_message(
                phone_number_id,
                to,
                wa_type,
                link=public_url,
                caption=caption,
                filename=filename,
                reply_to_message_id=reply_to_message_id,
            )
        except Exception:
            logger.warning(
                "WhatsApp link send failed for attachment %s; trying upload",
                att.id,
                exc_info=True,
            )

    media_id = upload_whatsapp_media(
        phone_number_id,
        file_bytes=file_bytes,
        mime_type=mime_type,
        wa_type=wa_type,
        filename=filename,
    )
    return send_whatsapp_media_message(
        phone_number_id,
        to,
        wa_type,
        media_id=media_id,
        caption=caption,
        filename=filename,
        reply_to_message_id=reply_to_message_id,
    )


def collect_assistant_file_attachments(assistant_message: Message) -> list[MessageAttachment]:
    """File attachments linked to this assistant message, oldest first."""
    return list(
        MessageAttachment.objects.filter(
            message=assistant_message,
            kind="file",
        )
        .exclude(file="")
        .order_by("created_at")
    )


def deliver_whatsapp_attachments(
    *,
    phone_number_id: str,
    to: str,
    assistant_message: Message,
    reply_to_message_id: str | None = None,
) -> list[str]:
    """
    Send all file attachments for the assistant turn. Returns outbound WAMIDs.
    Only the first message uses reply_to_message_id (thread context).
    """
    wamids: list[str] = []
    attachments = collect_assistant_file_attachments(assistant_message)
    for index, att in enumerate(attachments):
        try:
            wamid = send_attachment_to_whatsapp(
                phone_number_id,
                to,
                att,
                reply_to_message_id=reply_to_message_id if index == 0 else None,
            )
            if wamid:
                wamids.append(wamid)
        except Exception:
            logger.exception(
                "Failed to send WhatsApp media attachment_id=%s conversation message_id=%s",
                att.id,
                assistant_message.id,
            )
    return wamids
