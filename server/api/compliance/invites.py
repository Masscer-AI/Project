from __future__ import annotations

from datetime import timedelta
from html import escape
from typing import TypedDict

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


class InvitePrepChecklist(TypedDict):
    kind_label: str
    data: list[str]
    documents_now: list[str]
    documents_later: list[str]


def pld_invite_prep_checklist(person_type: str) -> InvitePrepChecklist:
    """What the invitee should gather before opening the signup link."""
    later = [
        "Poder notarial, si alguien actua en nombre de la contraparte",
        "Contratos, Excel, XML u otros documentos no obligatorios: se pueden cargar despues",
    ]
    if person_type == "persona_moral":
        return {
            "kind_label": "persona moral (empresa)",
            "data": [
                "Denominacion o razon social",
                "Fecha de constitucion, nacionalidad, RFC y giro",
                "Domicilio: pais, codigo postal, estado, municipio, ciudad, colonia, calle y numero exterior",
                "Representante legal: nombres, apellidos, tipo y numero de identificacion",
                "Beneficiario controlador: nombre de la persona fisica que controla la empresa",
            ],
            "documents_now": [
                "Acta constitutiva",
                "Constancia de situacion fiscal",
                "Comprobante de domicilio reciente (no mayor a 3 meses)",
                "Identificacion oficial del representante legal",
                "Identificacion del beneficiario controlador",
            ],
            "documents_later": later,
        }
    return {
        "kind_label": "persona fisica",
        "data": [
            "Nombres y apellidos",
            "Fecha y pais de nacimiento, nacionalidad",
            "RFC y CURP (obligatorios si tu nacionalidad es mexicana)",
            "Ocupacion / giro",
            "Domicilio: pais, codigo postal, estado, municipio, ciudad, colonia, calle y numero exterior",
            "Identificacion oficial: tipo (INE, pasaporte u otra) y numero",
            "Si no eres el beneficiario controlador: nombre de esa persona",
        ],
        "documents_now": [
            "Identificacion oficial con fotografia (INE o pasaporte)",
            "Constancia de CURP (si aplica)",
            "Constancia de situacion fiscal (RFC)",
            "Comprobante de domicilio reciente (no mayor a 3 meses)",
            "Identificacion del beneficiario controlador, solo si no eres tu",
        ],
        "documents_later": later,
    }


def _html_ul(items: list[str]) -> str:
    rows = "".join(f"<li>{escape(item)}</li>" for item in items)
    return f'<ul style="margin:8px 0 16px 20px;padding:0;">{rows}</ul>'


def send_pld_invite_email(
    *,
    invite_email: str,
    organization_name: str,
    signup_url: str,
    person_type: str,
) -> None:
    checklist = pld_invite_prep_checklist(person_type)
    org = escape(organization_name)
    url = escape(signup_url, quote=True)
    html = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.5; color:#222;">
            <h2>Completa tu expediente en Masscer</h2>
            <p>
                <strong>{org}</strong> te pidio completar tu expediente de
                cumplimiento (PLD/KYB) en Masscer como {escape(str(checklist["kind_label"]))}.
            </p>
            <p>
                Ten a la mano estos datos y documentos <strong>antes</strong> de abrir el
                enlace. Asi agilizas el alta: entras, capturas identificacion y cargas
                lo obligatorio. Lo no obligatorio se puede subir despues.
            </p>
            <h3 style="margin-bottom:4px;">Datos a tener listos</h3>
            {_html_ul(checklist["data"])}
            <h3 style="margin-bottom:4px;">Documentos para la primera etapa</h3>
            {_html_ul(checklist["documents_now"])}
            <h3 style="margin-bottom:4px;">Se pueden cargar despues</h3>
            {_html_ul(checklist["documents_later"])}
            <p>
                <a href="{url}" style="display:inline-block;padding:10px 16px;background:#6e5bff;color:#fff;text-decoration:none;border-radius:6px;">
                    Completar expediente
                </a>
            </p>
            <p>Si el boton no funciona, abre este enlace:</p>
            <p><a href="{url}">{url}</a></p>
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
