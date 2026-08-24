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

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import SignatureRequest, SignatureRequestStatus
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


class PublicSignatureRequestView(View):
    """
    Unauthenticated read endpoint for the external-signer widget page.
    Gated only by the unguessable SignatureRequest UUID in the URL, same
    pattern as messaging.SharedConversationView. Never exposes the
    signatory's email/RFC, other signatories, or organization-internal data
    beyond a display name — this link may be forwarded by whoever receives it.
    """

    def get(self, request, signature_request_id):
        try:
            sr = SignatureRequest.objects.select_related("organization").get(
                id=signature_request_id
            )
        except SignatureRequest.DoesNotExist:
            return JsonResponse(
                {"message": "Signature request not found", "status": 404}, status=404
            )

        return JsonResponse(
            {
                "id": str(sr.id),
                "status": sr.status,
                "title": sr.title or sr.get_document_kind_display(),
                "signatory_name": sr.signatory_name,
                "organization_name": sr.organization.name,
                "widget_id": sr.provider_widget_id or None,
                "widget_ready": bool(sr.provider_widget_id)
                and sr.status == SignatureRequestStatus.PENDING,
                "mifiel_environment": (
                    "sandbox" if "sandbox" in settings.MIFIEL_BASE_URL else "production"
                ),
            }
        )
