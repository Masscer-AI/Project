"""Meta WhatsApp Cloud API webhook signature (X-Hub-Signature-256)."""

from __future__ import annotations

import hashlib
import hmac


def verify_meta_webhook_signature(
    raw_body: bytes, signature_header: str, app_secret: str
) -> bool:
    """
    Validate ``X-Hub-Signature-256: sha256=<hex>`` using the app secret.
    """
    if not app_secret or not signature_header:
        return False
    expected = (
        "sha256="
        + hmac.new(
            app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature_header.strip())
