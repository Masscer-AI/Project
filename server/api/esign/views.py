"""
Mifiel webhook receiver.

Known gap: Mifiel does not sign outbound webhook calls (its own API docs list
`Authorizations: None` on every webhook event type), unlike the Meta/WhatsApp
webhook this app also receives (which is HMAC-verified via
`verify_meta_webhook_signature`). We compensate by never trusting the payload
alone: `process_mifiel_webhook_event` only acts on a `data.external_id` that
matches a SignatureRequest this server itself created and sent to Mifiel.
"""

from __future__ import annotations

import json
import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .tasks import process_mifiel_webhook_event

logger = logging.getLogger(__name__)


@csrf_exempt
def mifiel_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponse(status=400)

    logger.info("Received Mifiel webhook: event=%s", payload.get("event"))
    process_mifiel_webhook_event.delay(payload=payload)
    return HttpResponse(status=200)
