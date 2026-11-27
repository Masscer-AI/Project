import logging

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from api.authenticate.models import OrganizationInvite, RoleAssignment, UserProfile

logger = logging.getLogger(__name__)

ACCEPTABLE_STATUSES = (
    OrganizationInvite.Status.PENDING,
    OrganizationInvite.Status.EXPIRED,
)


class InviteAcceptError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def accept_organization_invite(
    invite: OrganizationInvite,
    *,
    password: str | None,
    source: str,
    allow_expired: bool = False,
) -> tuple[OrganizationInvite, User, bool]:
    """
    Create the invited user and mark the invite accepted.

    ``password`` None stores an unusable password. Queue the welcome WhatsApp
    when this returns ``enqueue_welcome`` True.
    """
    enqueue_welcome = False
    user = None
    invite_pk = None
    with transaction.atomic():
        invite_locked = OrganizationInvite.objects.select_for_update().select_related(
            "organization"
        ).get(pk=invite.pk)
        if invite_locked.status not in ACCEPTABLE_STATUSES:
            raise InviteAcceptError("invite-cannot-be-accepted")
        if (
            invite_locked.status == OrganizationInvite.Status.EXPIRED
            and not allow_expired
        ):
            raise InviteAcceptError("invalid-or-expired-invite")
        if (
            invite_locked.status == OrganizationInvite.Status.PENDING
            and invite_locked.is_invite_expired()
            and not allow_expired
        ):
            invite_locked.mark_expired_if_needed()
            raise InviteAcceptError("invalid-or-expired-invite")
        if User.objects.filter(email__iexact=invite_locked.email).exists():
            raise InviteAcceptError("email-already-registered")

        email = invite_locked.email
        base_username = email.split("@")[0] or "member"
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
        profile.organization = invite_locked.organization
        profile.name = invite_locked.name or ""
        profile.bio = invite_locked.bio or ""
        profile.intake = {}
        profile.expires_at = invite_locked.profile_expires_at
        if invite_locked.send_welcome_message:
            from api.authenticate.phone_numbers import (
                phone_entries_from_whatsapp_digits,
                unused_phone_entries,
            )

            entries = unused_phone_entries(
                phone_entries_from_whatsapp_digits(
                    invite_locked.welcome_phones or []
                ),
                exclude_user_id=user.id,
            )
            if entries:
                profile.phone_numbers = entries
        profile.save()

        if invite_locked.role_id:
            RoleAssignment.objects.create(
                user=user,
                organization=invite_locked.organization,
                role_id=invite_locked.role_id,
                from_date=timezone.now().date(),
            )

        now = timezone.now()
        invite_locked.status = OrganizationInvite.Status.ACCEPTED
        invite_locked.accepted_at = now
        invite_locked.accepted_user = user
        invite_locked.save(
            update_fields=[
                "status",
                "accepted_at",
                "accepted_user",
                "updated_at",
            ]
        )
        enqueue_welcome = bool(invite_locked.send_welcome_message)
        invite_pk = str(invite_locked.id)
        invite = invite_locked

    logger.info(
        "organization_invite accepted invite=%s user=%s enqueue_welcome=%s source=%s",
        invite_pk,
        user.id,
        enqueue_welcome,
        source,
    )
    return invite, user, enqueue_welcome


def enqueue_invite_welcome(invite: OrganizationInvite, *, source: str) -> None:
    from api.authenticate.tasks import send_invite_welcome_whatsapp

    send_invite_welcome_whatsapp.delay(str(invite.id))
    logger.info(
        "organization_invite welcome_queued invite=%s source=%s",
        invite.id,
        source,
    )
