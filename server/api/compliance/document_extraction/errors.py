from __future__ import annotations


def public_extraction_error(exc: BaseException) -> str:
    """Stable invitee-facing code stored on PLDExpedientDocument.extraction_error."""
    text = str(exc or "").strip()
    lowered = text.casefold()
    if "empty" in lowered:
        return "file-empty"
    if (
        "not available" in lowered
        or "no such file" in lowered
        or "cannot be reopened" in lowered
    ):
        return "file-unavailable"
    if "structured output" in lowered:
        return "no-structured-output"
    if any(
        token in lowered
        for token in (
            "unreadable",
            "cannot open",
            "invalid pdf",
            "unsupported",
            "failed to analyze",
        )
    ):
        return "unreadable"
    return "extraction-failed"
