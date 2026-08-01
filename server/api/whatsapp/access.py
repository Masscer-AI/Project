"""
Inbound access control for WhatsApp business lines.

Restricted modes match the Meta sender phone against UserProfile.phone_numbers
for users in the allowed set (org / roles / single user).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from django.contrib.auth.models import User

from api.authenticate.org_membership import (
    active_role_assignments_for_org,
    iter_organization_member_users,
    user_belongs_to_organization,
)
from api.authenticate.phone_numbers import (
    parse_phone_numbers,
    whatsapp_phone_match_keys,
)
from api.whatsapp.conversations import (
    get_or_create_ws_contact,
    resolved_organization_for_ws_number,
)
from api.whatsapp.models import WSContact, WSNumber

_DIGITS_RE = re.compile(r"[^\d]")

WHATSAPP_RESTRICTED_ACCESS_REPLY = (
    "Sorry, this agent has a restricted access, if you thing this is a mistake, "
    "contact your organization administrator."
)


@dataclass(frozen=True)
class WhatsAppSenderAccessResult:
    allowed: bool
    user: User | None = None


def _digits_only(value: str) -> str:
    return _DIGITS_RE.sub("", value or "")


def _profile_whatsapp_match_set(user: User) -> set[str]:
    """Profile phones expanded for Meta Mexico (521…) ↔ E.164 (52…) equivalence."""
    try:
        profile = user.profile
    except Exception:
        return set()
    return parse_phone_numbers(
        getattr(profile, "_phone_numbers", None)
    ).as_whatsapp_match_set()


def _match_user_by_phone(candidates: list[User], phone_digits: str) -> User | None:
    inbound_keys = whatsapp_phone_match_keys(phone_digits)
    if not inbound_keys:
        return None
    for user in candidates:
        if inbound_keys & _profile_whatsapp_match_set(user):
            return user
    return None


def _candidate_users_for_roles(ws_number: WSNumber, organization) -> list[User]:
    role_ids = list(ws_number.allowed_roles.values_list("id", flat=True))
    if not role_ids:
        return []
    user_ids = {
        assignment.user_id
        for assignment in active_role_assignments_for_org(organization)
        if assignment.role_id in role_ids
    }
    if not user_ids:
        return []
    return list(User.objects.filter(id__in=user_ids).order_by("id"))


def resolve_whatsapp_sender_access(
    ws_number: WSNumber,
    phone_digits: str,
) -> WhatsAppSenderAccessResult:
    """
    Decide whether ``phone_digits`` may message ``ws_number``.

    On restricted allow, ``user`` is the matched organization member (for autolink).
    Public allows with ``user=None``.
    """
    mode = (ws_number.access_mode or WSNumber.ACCESS_MODE_PUBLIC).strip()
    phone = _digits_only(phone_digits)

    if mode == WSNumber.ACCESS_MODE_PUBLIC:
        return WhatsAppSenderAccessResult(allowed=True, user=None)

    org = resolved_organization_for_ws_number(ws_number)
    if not org:
        return WhatsAppSenderAccessResult(allowed=False, user=None)

    if mode == WSNumber.ACCESS_MODE_ORGANIZATION:
        candidates = iter_organization_member_users(org)
        matched = _match_user_by_phone(candidates, phone)
        if matched:
            return WhatsAppSenderAccessResult(allowed=True, user=matched)
        return WhatsAppSenderAccessResult(allowed=False, user=None)

    if mode == WSNumber.ACCESS_MODE_ROLES:
        candidates = _candidate_users_for_roles(ws_number, org)
        matched = _match_user_by_phone(candidates, phone)
        if matched:
            return WhatsAppSenderAccessResult(allowed=True, user=matched)
        return WhatsAppSenderAccessResult(allowed=False, user=None)

    if mode == WSNumber.ACCESS_MODE_USER:
        access_user = ws_number.access_user
        if not access_user or not user_belongs_to_organization(access_user, org):
            return WhatsAppSenderAccessResult(allowed=False, user=None)
        matched = _match_user_by_phone([access_user], phone)
        if matched:
            return WhatsAppSenderAccessResult(allowed=True, user=matched)
        return WhatsAppSenderAccessResult(allowed=False, user=None)

    return WhatsAppSenderAccessResult(allowed=False, user=None)


def ensure_ws_contact_for_inbound(
    ws_number: WSNumber,
    phone_digits: str,
    *,
    user: User | None = None,
) -> WSContact:
    """
    Get or create the stable contact for this inbound phone.

    When ``user`` is provided and the contact has no linked user yet, autolink it.
    """
    contact = get_or_create_ws_contact(ws_number, phone_digits)
    if user is not None and contact.user_id is None:
        contact.user = user
        contact.save(update_fields=["user", "updated_at"])
    return contact
