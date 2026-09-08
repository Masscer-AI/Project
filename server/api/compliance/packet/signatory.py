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
    """People who must sign the identification packet (same PDF, distinct emails)."""
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
        representative = meta.get("representative")
        rep_name = ""
        rep_rfc = rfc
        if isinstance(representative, dict):
            rep_name = _join(
                representative.get("given_names"),
                representative.get("surnames")
                or _join(
                    representative.get("paternal_surname"),
                    representative.get("maternal_surname"),
                ),
            )
            rep_rfc = str(representative.get("rfc") or rfc).strip().upper()
        if not rep_name:
            rep_name = entity_display_name(entity)
        add(
            name=rep_name,
            email=primary_email,
            rfc=rep_rfc,
            role="representative",
            user=entity.user,
        )
        for item in _controller_dicts(meta):
            add(
                name=str(item.get("name") or ""),
                email=str(item.get("email") or ""),
                rfc=str(item.get("rfc") or ""),
                role="controller",
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
        if meta.get("is_own_controller") is not True:
            for item in _controller_dicts(meta):
                add(
                    name=str(item.get("name") or ""),
                    email=str(item.get("email") or ""),
                    rfc=str(item.get("rfc") or ""),
                    role="controller",
                )
    return rows


def missing_controller_signers(entity) -> list[str]:
    """Named controllers that still need an email before we can send the packet."""
    meta = entity.metadata if isinstance(entity.metadata, dict) else {}
    if entity.person_type != "persona_moral" and meta.get("is_own_controller") is not False:
        return []
    missing = []
    for item in _controller_dicts(meta):
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        if not _email_ok(item.get("email")):
            missing.append(name)
    return missing


def _controller_dicts(meta: dict) -> list[dict]:
    raw = meta.get("controllers")
    rows = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and str(item.get("name") or "").strip():
                rows.append(item)
    if rows:
        return rows
    single = meta.get("controller")
    if isinstance(single, dict) and str(single.get("name") or "").strip():
        return [single]
    return []
