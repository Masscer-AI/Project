"""
Meta Graph API helpers to subscribe a WABA app to webhooks (Darwin-style admin flow).

Uses WHATSAPP_GRAPH_API_TOKEN (system user), WHATSAPP_APP_SECRET for app-level
/subscriptions calls, WHATSAPP_WEBHOOK_VERIFY_TOKEN, and settings.API_BASE_URL
(resolved from API_BASE_URL or API_URL) to build the callback URL served by
api.whatsapp.views.webhook.
"""

from __future__ import annotations

from typing import Any

import requests
from django.conf import settings

_GRAPH_VERSION = "v21.0"
_GRAPH_BASE = f"https://graph.facebook.com/{_GRAPH_VERSION}"


def _graph_token() -> str:
    token = (getattr(settings, "WHATSAPP_GRAPH_API_TOKEN", "") or "").strip()
    if not token:
        raise RuntimeError("WHATSAPP_GRAPH_API_TOKEN is not configured.")
    return token


def _app_secret() -> str:
    secret = (getattr(settings, "WHATSAPP_APP_SECRET", "") or "").strip()
    if not secret:
        raise RuntimeError(
            "WHATSAPP_APP_SECRET is required to subscribe webhook fields via the Graph API."
        )
    return secret


def whatsapp_webhook_callback_url() -> str:
    base = (getattr(settings, "API_BASE_URL", "") or "").strip().rstrip("/")
    if not base:
        raise RuntimeError(
            "Set API_BASE_URL or API_URL to your public HTTPS API origin (e.g. your dev tunnel URL) "
            "so Meta can call GET/POST /v1/whatsapp/webhook."
        )
    return f"{base}/v1/whatsapp/webhook"


def _graph_request(
    method: str,
    path: str,
    *,
    token: str,
    json_body: dict[str, Any] | None = None,
) -> requests.Response:
    url = f"{_GRAPH_BASE}/{path.lstrip('/')}"
    response = requests.request(
        method,
        url,
        headers={"Authorization": f"Bearer {token}"},
        json=json_body,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"Graph API error {response.status_code}: {response.text}")
    return response


def _app_token(app_id: str) -> str:
    return f"{app_id}|{_app_secret()}"


def fetch_waba_id_for_phone_number_id(phone_number_id: str) -> str | None:
    """Resolve WhatsApp Business Account id from a business phone number id."""
    pid = phone_number_id.strip()
    if not pid:
        return None
    url = f"{_GRAPH_BASE}/{pid}"
    r = requests.get(
        url,
        params={"fields": "whatsapp_business_account{id}"},
        headers={"Authorization": f"Bearer {_graph_token()}"},
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"Graph API error {r.status_code}: {r.text}")
    data = r.json()
    inner = data.get("whatsapp_business_account") or {}
    wid = inner.get("id")
    return str(wid) if wid else None


def resolve_waba_id_for_ws_number(ws_number) -> str | None:
    """Prefer stored waba_id; otherwise resolve from platform_id (phone number id)."""
    raw = getattr(ws_number, "waba_id", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    pid = (getattr(ws_number, "platform_id", None) or "").strip()
    if not pid:
        return None
    return fetch_waba_id_for_phone_number_id(pid)


def subscribe_waba_to_app(waba_id: str) -> None:
    """POST {waba_id}/subscribed_apps — attach your Meta app to the WABA."""
    wid = waba_id.strip()
    if not wid:
        raise RuntimeError("waba_id is empty.")
    _graph_request("POST", f"{wid}/subscribed_apps", token=_graph_token(), json_body=None)


def get_subscribed_apps(waba_id: str) -> list[dict[str, Any]]:
    wid = waba_id.strip()
    if not wid:
        raise RuntimeError("waba_id is empty.")
    response = _graph_request(
        "GET", f"{wid}/subscribed_apps", token=_graph_token(), json_body=None
    )
    return list(response.json().get("data") or [])


def subscribe_app_webhook_fields(app_id: str, callback_url: str, verify_token: str) -> None:
    """POST {app_id}/subscriptions for object whatsapp_business_account (app access token)."""
    aid = app_id.strip()
    if not aid:
        raise RuntimeError("app_id is empty.")
    _graph_request(
        "POST",
        f"{aid}/subscriptions",
        token=_app_token(aid),
        json_body={
            "object": "whatsapp_business_account",
            "callback_url": callback_url,
            "verify_token": verify_token,
            "fields": ["messages"],
        },
    )


def get_app_webhook_subscriptions(app_id: str) -> list[dict[str, Any]]:
    aid = app_id.strip()
    if not aid:
        raise RuntimeError("app_id is empty.")
    response = _graph_request(
        "GET", f"{aid}/subscriptions", token=_app_token(aid), json_body=None
    )
    return list(response.json().get("data") or [])


def register_phone_number(phone_number_id: str, pin: str) -> None:
    pid = phone_number_id.strip()
    if not pid:
        raise RuntimeError("platform_id (phone number id) is empty.")
    _graph_request(
        "POST",
        f"{pid}/register",
        token=_graph_token(),
        json_body={"messaging_product": "whatsapp", "pin": pin},
    )


def format_subscription_summary(subscriptions: list[dict[str, Any]]) -> str:
    wa_sub = next(
        (s for s in subscriptions if s.get("object") == "whatsapp_business_account"),
        None,
    )
    if not wa_sub:
        return "No whatsapp_business_account webhook subscription found for this app."
    fields_raw = wa_sub.get("fields") or []
    if isinstance(fields_raw, list):
        names: list[str] = []
        for f in fields_raw:
            if isinstance(f, dict) and f.get("name"):
                names.append(str(f["name"]))
            elif isinstance(f, str):
                names.append(f)
        fields = ", ".join(names) if names else "(none)"
    else:
        fields = str(fields_raw)
    callback = wa_sub.get("callback_url", "")
    active = wa_sub.get("active")
    return f"callback={callback} | active={active} | fields=[{fields}]"


def first_subscribed_app_id(apps: list[dict[str, Any]]) -> str | None:
    for row in apps:
        data = row.get("whatsapp_business_api_data") or {}
        app_id = data.get("id")
        if app_id:
            return str(app_id)
    return None


def is_already_registered_error(exc: BaseException) -> bool:
    return "133005" in str(exc)
