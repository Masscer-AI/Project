"""MessageAttachment visibility ACL (personal / organization / roles / link)."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import User
from django.db.models import Q

from api.ai_layers.access import (
    get_active_role_ids,
    get_user_organizations_for_access,
)
from api.authenticate.models import Organization, Role
from api.messaging.models import MessageAttachment
from api.rag.access import parse_role_ids, resolve_user_organization

VISIBILITY_PERSONAL = MessageAttachment.Visibility.PERSONAL
VISIBILITY_ORGANIZATION = MessageAttachment.Visibility.ORGANIZATION
VISIBILITY_ROLES = MessageAttachment.Visibility.ROLES
VISIBILITY_LINK = MessageAttachment.Visibility.LINK


def compliance_evidence_q() -> Q:
    """Attachments that belong to a KYB folio / compliance conversation."""
    return (
        Q(metadata__contains={"compliance": True})
        | Q(folio_document__isnull=False)
        | Q(conversation__metadata__contains={"surface": "compliance"})
    )

def _resolve_user(*, user=None, user_id: int | None = None):
    if user is not None:
        return user
    if user_id is None:
        return None
    return User.objects.filter(pk=int(user_id)).first()

def attachments_visible_q(
    *,
    user=None,
    user_id: int | None = None,
    conversation_id: str | None = None,
    organization_id: int | None = None,
    include_compliance_evidence: bool = False,
) -> Q:
    """
    Attachments the actor may list/read.

    Authenticated: personal (owner) + org/roles ACL + link files in their orgs
    (or owned by them) + everything in the current conversation.
    Anonymous (widget / unlinked WhatsApp): current conversation only.

    KYB expediente files are excluded unless include_compliance_evidence=True
    (compliance assistant tools only).
    """
    del organization_id
    actor = _resolve_user(user=user, user_id=user_id)
    if actor is None:
        if conversation_id:
            q = Q(conversation_id=conversation_id)
        else:
            raise ValueError("list_attachments requires user_id or conversation_id")
        if not include_compliance_evidence:
            q = q & ~compliance_evidence_q()
        return q

    q = Q(visibility=VISIBILITY_PERSONAL, user=actor)

    orgs = get_user_organizations_for_access(actor)
    org_ids = [o.id for o in orgs]
    if org_ids:
        q |= Q(visibility=VISIBILITY_ORGANIZATION, organization_id__in=org_ids)
        q |= Q(visibility=VISIBILITY_LINK, organization_id__in=org_ids)

    q |= Q(visibility=VISIBILITY_LINK, user=actor)

    for org in orgs:
        if org.owner_id == actor.id:
            q |= Q(visibility=VISIBILITY_ROLES, organization_id=org.id)
            continue
        role_ids = list(get_active_role_ids(actor, org))
        if role_ids:
            q |= Q(
                visibility=VISIBILITY_ROLES,
                organization_id=org.id,
                allowed_roles__in=role_ids,
            )

    if conversation_id:
        q |= Q(conversation_id=conversation_id)

    if not include_compliance_evidence:
        q = q & ~compliance_evidence_q()

    return q

def user_can_access_attachment(
    att,
    *,
    user=None,
    user_id: int | None = None,
    conversation_id: str | None = None,
    organization_id: int | None = None,
    include_compliance_evidence: bool = False,
) -> bool:
    """Whether read/send tools may use this attachment."""
    if att is None:
        return False
    actor = _resolve_user(user=user, user_id=user_id)
    return MessageAttachment.objects.filter(
        attachments_visible_q(
            user=actor,
            conversation_id=conversation_id,
            organization_id=organization_id,
            include_compliance_evidence=include_compliance_evidence,
        ),
        pk=att.pk,
    ).exists()

def _attachment_organization(att):
    org = getattr(att, "organization", None)
    if org is not None:
        return org
    conv = getattr(att, "conversation", None)
    if conv is not None:
        return getattr(conv, "organization", None)
    return None

def user_can_manage_attachment(att, user) -> bool:
    """
    Change visibility or delete from the UI: conversation owner, organization
    owner, or the attachment owner (fallback for widget / WhatsApp).
    """
    if not user or not att:
        return False
    if att.user_id is not None and int(att.user_id) == int(user.id):
        return True

    conv = getattr(att, "conversation", None)
    if conv is not None and conv.user_id is not None and int(conv.user_id) == int(user.id):
        return True

    org = _attachment_organization(att)
    if org is not None and org.owner_id == user.id:
        return True
    return False

def user_can_agent_update_attachment_visibility(att, user) -> bool:
    """
    Agent tool gate: if the agent has update_attachment_visibility, any member
    of the attachment's organization may change ACL. UI manage permission is
    not required. Outsiders still cannot.
    """
    if user_can_manage_attachment(att, user):
        return True
    if not user or not att:
        return False
    org = _attachment_organization(att)
    if org is None:
        return False
    return org.id in {o.id for o in get_user_organizations_for_access(user)}

def attachment_belongs_to_payload(
    att: MessageAttachment, user: User | None = None
) -> dict[str, Any]:
    vis = att.visibility or VISIBILITY_PERSONAL
    if vis == VISIBILITY_PERSONAL:
        if user is not None and att.user_id == getattr(user, "id", None):
            return {"type": "you"}
        return {"type": "personal", "created_by_id": att.user_id}

    org = getattr(att, "organization", None)
    org_name = getattr(org, "name", None) if org is not None else None
    org_id = str(att.organization_id) if att.organization_id else None

    if vis == VISIBILITY_ORGANIZATION:
        return {
            "type": "organization",
            "organization": org_name,
            "organization_id": org_id,
        }
    if vis == VISIBILITY_LINK:
        return {
            "type": "link",
            "organization": org_name,
            "organization_id": org_id,
        }

    roles = [{"id": str(r.id), "name": r.name} for r in att.allowed_roles.all()]
    return {
        "type": "roles",
        "organization": org_name,
        "organization_id": org_id,
        "roles": roles,
    }

def _home_organization(att: MessageAttachment, user: User) -> Organization | None:
    if att.organization_id:
        return att.organization
    conv = getattr(att, "conversation", None)
    if conv is not None and getattr(conv, "organization_id", None):
        return conv.organization
    return resolve_user_organization(user)

def apply_attachment_ownership(
    att: MessageAttachment,
    *,
    user: User,
    visibility: str | None = None,
    role_ids: list[str] | None = None,
    organization: Organization | None = None,
) -> None:
    """
    Set visibility ACL fields. Caller must already be allowed to manage.
    """
    vis = (visibility or VISIBILITY_PERSONAL).strip().lower()
    if vis not in {
        VISIBILITY_PERSONAL,
        VISIBILITY_ORGANIZATION,
        VISIBILITY_ROLES,
        VISIBILITY_LINK,
    }:
        raise ValueError(
            "visibility must be one of: personal, organization, roles, link"
        )

    roles = parse_role_ids(role_ids)
    org = organization or _home_organization(att, user)

    if vis == VISIBILITY_PERSONAL:
        att.visibility = VISIBILITY_PERSONAL
        att.organization = None
        att.save(update_fields=["visibility", "organization"])
        att.allowed_roles.clear()
        return

    if vis == VISIBILITY_LINK:
        att.visibility = VISIBILITY_LINK
        att.organization = org
        att.save(update_fields=["visibility", "organization"])
        att.allowed_roles.clear()
        return

    if not org:
        raise ValueError("Organization is required for organization/roles visibility.")

    if vis == VISIBILITY_ORGANIZATION:
        att.visibility = VISIBILITY_ORGANIZATION
        att.organization = org
        att.save(update_fields=["visibility", "organization"])
        att.allowed_roles.clear()
        return

    if not roles:
        raise ValueError("role_ids is required when visibility is roles.")

    role_qs = Role.objects.filter(id__in=roles, organization=org, enabled=True)
    found = list(role_qs)
    if len(found) != len(set(roles)):
        raise ValueError("One or more role_ids are invalid for this organization.")

    att.visibility = VISIBILITY_ROLES
    att.organization = org
    att.save(update_fields=["visibility", "organization"])
    att.allowed_roles.set(found)
