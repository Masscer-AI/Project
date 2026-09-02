from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from api.authenticate.models import UserProfile, hash_organization_invite_token
from api.compliance.models import PLDEntity, PLDInvite
from api.utils.email_service import EmailService

INVITE_TTL_DAYS = 7


def entity_display_name(entity: PLDEntity) -> str:
    meta = entity.metadata if isinstance(entity.metadata, dict) else {}
    name = meta.get("legal_name") or meta.get("name") or ""
    return str(name).strip() or str(entity.id)


def latest_invite_payload(entity: PLDEntity) -> dict | None:
    invite = entity.invites.order_by("-created_at").first()
    if not invite:
        return None
    return {
        "status": invite.status,
        "invite_expires_at": invite.invite_expires_at.isoformat()
        if invite.invite_expires_at
        else None,
        "accepted_at": invite.accepted_at.isoformat() if invite.accepted_at else None,
        "email": invite.email,
    }


def create_or_rotate_pending_invite(*, entity: PLDEntity, invited_by: User) -> tuple[PLDInvite, str]:
    email = (entity.email or "").strip().lower()
    if not email:
        raise ValueError("email is required")
    now = timezone.now()
    deadline = now + timedelta(days=INVITE_TTL_DAYS)
    raw_token = PLDInvite.generate_raw_token()
    digest = hash_organization_invite_token(raw_token)

    with transaction.atomic():
        pending = (
            PLDInvite.objects.select_for_update()
            .filter(entity=entity, status=PLDInvite.Status.PENDING)
            .first()
        )
        if pending:
            pending.email = email
            pending.invited_by = invited_by
            pending.token_hash = digest
            pending.invite_expires_at = deadline
            pending.save(
                update_fields=[
                    "email",
                    "invited_by",
                    "token_hash",
                    "invite_expires_at",
                    "updated_at",
                ]
            )
            return pending, raw_token

        invite = PLDInvite.objects.create(
            organization=entity.organization,
            entity=entity,
            email=email,
            invited_by=invited_by,
            token_hash=digest,
            status=PLDInvite.Status.PENDING,
            invite_expires_at=deadline,
        )
        return invite, raw_token


def send_pld_invite_email(*, invite_email: str, organization_name: str, signup_url: str) -> None:
    html = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.5;">
            <h2>Completa tu expediente en Masscer</h2>
            <p>
                <strong>{organization_name}</strong> te pidio completar tu expediente de
                cumplimiento (PLD/KYB) en Masscer.
            </p>
            <p>
                <a href="{signup_url}" style="display:inline-block;padding:10px 16px;background:#6e5bff;color:#fff;text-decoration:none;border-radius:6px;">
                    Completar expediente
                </a>
            </p>
            <p>Si el boton no funciona, abre este enlace:</p>
            <p><a href="{signup_url}">{signup_url}</a></p>
            <p>Si no esperabas este correo, puedes ignorarlo.</p>
        </div>
    """.strip()
    email_service = EmailService()
    email_service.send_email(
        to=invite_email,
        subject=f"Completa tu expediente con {organization_name}",
        html=html,
        from_name="Masscer",
    )


def public_invite_payload(invite: PLDInvite) -> dict:
    invite.mark_expired_if_needed()
    invite.refresh_from_db()
    if invite.status != PLDInvite.Status.PENDING or invite.is_invite_expired():
        return {"invite_valid": False, "error": "invalid-or-expired-invite"}

    email_registered = User.objects.filter(email__iexact=invite.email).exists()
    return {
        "invite_valid": not email_registered,
        "invite_kind": "pld",
        "email_already_registered": email_registered,
        "email": invite.email,
        "organization": {
            "id": str(invite.organization_id),
            "name": invite.organization.name,
        },
        "entity_name": entity_display_name(invite.entity),
        "invite_expires_at": invite.invite_expires_at.isoformat(),
        "error": None if not email_registered else "email-already-registered",
    }


def register_user_from_pld_invite(invite: PLDInvite, password: str) -> User:
    email = invite.email
    base_username = email.split("@")[0] or "user"
    username = base_username
    suffix = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{suffix}"
        suffix += 1

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.organization = None
    profile.name = entity_display_name(invite.entity)
    profile.intake = {}
    profile.save()
    return user


def accept_pld_invite(*, invite: PLDInvite, user: User) -> PLDInvite:
    if user.email.lower() != invite.email.lower():
        raise ValueError("email-mismatch")
    now = timezone.now()
    invite.status = PLDInvite.Status.ACCEPTED
    invite.accepted_at = now
    invite.accepted_user = user
    invite.save(
        update_fields=["status", "accepted_at", "accepted_user", "updated_at"]
    )
    entity = invite.entity
    entity.user = user
    entity.save(update_fields=["user", "updated_at"])
    return invite
