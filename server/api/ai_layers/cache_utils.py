from __future__ import annotations

from django.core.cache import cache
from django.db.models import Q
from django.contrib.auth.models import User


AGENT_LIST_VERSION_TIMEOUT_SECONDS = 60 * 60 * 24 * 30  # 30 days


def _agent_list_version_key(user_id: int, org_id: str) -> str:
    return f"agent_list_v_{user_id}_{org_id}"


def get_agent_list_cache_key(user_id: int, org_id: str) -> str:
    """
    Cache key for GET /agents response.

    We use a per-(user, org) monotonically increasing version so that invalidation
    does not require wildcard deletes (which not all cache backends support).
    """
    v = cache.get(_agent_list_version_key(user_id, org_id), 1)
    try:
        v = int(v)
    except Exception:
        v = 1
    return f"agent_data_{user_id}_{org_id}_v{v}"


def bump_agent_list_version(user_id: int, org_id: str) -> None:
    key = _agent_list_version_key(user_id, org_id)
    v = cache.get(key, 1)
    try:
        v = int(v)
    except Exception:
        v = 1
    cache.set(key, v + 1, timeout=AGENT_LIST_VERSION_TIMEOUT_SECONDS)


def bump_agent_list_version_for_user(user_id: int, org_id: str | None) -> None:
    bump_agent_list_version(user_id, "no_org")
    if org_id:
        bump_agent_list_version(user_id, str(org_id))


def bump_agent_list_version_for_org_members(organization) -> None:
    """
    Bump agent list versions for all org members + owner.
    """
    if not organization:
        return
    org_id = str(getattr(organization, "id", organization))
    from api.authenticate.models import Organization as OrganizationModel, UserProfile

    try:
        org = (
            organization
            if hasattr(organization, "id")
            else OrganizationModel.objects.get(id=organization)
        )
    except OrganizationModel.DoesNotExist:
        return

    members = User.objects.filter(
        Q(profile__organization=org) | Q(id=org.owner_id)
    ).distinct()
    for u in members:
        bump_agent_list_version_for_user(u.id, org_id)

