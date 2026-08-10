"""Document visibility ACL (personal / organization / roles)."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Q

from api.ai_layers.access import (
    get_active_role_ids,
    get_user_organization,
    get_user_organizations_for_access,
)
from api.authenticate.models import Organization, Role
from api.authenticate.services import FeatureFlagService
from api.rag.models import Document


VISIBILITY_PERSONAL = Document.Visibility.PERSONAL
VISIBILITY_ORGANIZATION = Document.Visibility.ORGANIZATION
VISIBILITY_ROLES = Document.Visibility.ROLES


def user_has_train_agents(user) -> bool:
    organization = get_user_organization(user)
    if not organization and user:
        organization = Organization.objects.filter(owner=user).first()
    if not organization:
        return False
    enabled, _ = FeatureFlagService.is_feature_enabled(
        "train-agents", organization=organization, user=user
    )
    return bool(enabled)


def document_owner_user_id(doc: Document) -> int | None:
    if getattr(doc, "created_by_id", None):
        return doc.created_by_id
    return getattr(getattr(doc, "collection", None), "user_id", None)


def documents_accessible_q(user) -> Q:
    """
    Q filter for documents the user may see in the knowledge base / attach picker.
    """
    if not user:
        return Q(pk__in=[])

    q = Q(visibility=VISIBILITY_PERSONAL, created_by=user) | Q(
        visibility=VISIBILITY_PERSONAL,
        created_by__isnull=True,
        collection__user=user,
    )

    orgs = get_user_organizations_for_access(user)
    if not orgs:
        return q

    org_ids = [o.id for o in orgs]
    q |= Q(visibility=VISIBILITY_ORGANIZATION, organization_id__in=org_ids)

    for org in orgs:
        if org.owner_id == user.id:
            q |= Q(visibility=VISIBILITY_ROLES, organization_id=org.id)
            continue
        role_ids = list(get_active_role_ids(user, org))
        if role_ids:
            q |= Q(
                visibility=VISIBILITY_ROLES,
                organization_id=org.id,
                allowed_roles__in=role_ids,
            )

    return q


def user_can_access_document(user, doc: Document) -> bool:
    if not user or not doc:
        return False
    return Document.objects.filter(documents_accessible_q(user), pk=doc.pk).exists()


def user_can_manage_document(user, doc: Document) -> bool:
    """Manage requires train-agents plus access (same visibility rules)."""
    if not user_has_train_agents(user):
        return False
    return user_can_access_document(user, doc)


def resolve_user_organization(user) -> Organization | None:
    if not user:
        return None
    owned = Organization.objects.filter(owner=user).first()
    if owned:
        return owned
    return get_user_organization(user)


def parse_role_ids(raw) -> list[str]:
    """Normalize role_ids from JSON list, comma-separated string, or repeated form values."""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("["):
        import json

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in text.split(",") if part.strip()]


def apply_document_ownership(
    document: Document,
    *,
    user: User,
    visibility: str | None = None,
    role_ids: list[str] | None = None,
    organization: Organization | None = None,
) -> None:
    """
    Set visibility ACL fields on a document and save.

    Raises ValueError on invalid combinations.
    """
    org = organization or resolve_user_organization(user)
    vis = (visibility or VISIBILITY_PERSONAL).strip().lower()
    if vis not in {
        VISIBILITY_PERSONAL,
        VISIBILITY_ORGANIZATION,
        VISIBILITY_ROLES,
    }:
        raise ValueError(
            "visibility must be one of: personal, organization, roles"
        )

    roles = parse_role_ids(role_ids)

    if not document.created_by_id:
        document.created_by = user

    if vis == VISIBILITY_PERSONAL:
        document.visibility = VISIBILITY_PERSONAL
        document.organization = None
        document.save()
        document.allowed_roles.clear()
        return

    if not org:
        raise ValueError("Organization is required for organization/roles visibility.")

    if vis == VISIBILITY_ORGANIZATION:
        document.visibility = VISIBILITY_ORGANIZATION
        document.organization = org
        document.save()
        document.allowed_roles.clear()
        return

    # roles
    if not roles:
        raise ValueError("role_ids is required when visibility is roles.")

    role_qs = Role.objects.filter(id__in=roles, organization=org, enabled=True)
    found = list(role_qs)
    if len(found) != len(set(roles)):
        raise ValueError("One or more role_ids are invalid for this organization.")

    document.visibility = VISIBILITY_ROLES
    document.organization = org
    document.save()
    document.allowed_roles.set(found)
