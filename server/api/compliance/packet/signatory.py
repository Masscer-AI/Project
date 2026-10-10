from __future__ import annotations

from api.compliance.invites import entity_display_name


def _join(*parts: str | None) -> str:
    return " ".join(part.strip() for part in parts if part and str(part).strip())


def _email_ok(value: str | None) -> bool:
    text = (value or "").strip()
    return "@" in text and "." in text.split("@")[-1]


def resolve_signatory(entity) -> dict | None:
    signers = resolve_signatories(entity)
    return signers[0] if signers else None


def resolve_signatories(entity) -> list[dict]:
    """The company signs a company file. A person signs their own file."""
    meta = entity.metadata if isinstance(entity.metadata, dict) else {}
    primary_email = (
        (entity.email or "").strip()
        or str(meta.get("email") or "").strip()
        or (getattr(entity.user, "email", "") or "").strip()
    )
    rows: list[dict] = []
    seen: set[str] = set()

    def add(*, name: str, email: str, rfc: str, role: str, user=None) -> None:
        name = (name or "").strip()
        email = (email or "").strip()
        if not name or not _email_ok(email):
            return
        key = email.casefold()
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "name": name[:255],
                "email": email,
                "rfc": (rfc or "").strip().upper()[:13],
                "role": role,
                "user": user,
            }
        )

    rfc = str(meta.get("rfc") or "").strip().upper()
    if entity.person_type == "persona_moral":
        add(
            name=entity_display_name(entity),
            email=primary_email,
            rfc=rfc,
            role="company",
            user=entity.user,
        )
    else:
        name = entity_display_name(entity)
        if not name or name == str(entity.id):
            name = _join(
                meta.get("given_names"),
                meta.get("surnames")
                or _join(meta.get("paternal_surname"), meta.get("maternal_surname")),
            )
        add(
            name=name,
            email=primary_email,
            rfc=rfc,
            role="counterparty",
            user=entity.user,
        )
    return rows
