from __future__ import annotations

import logging

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_user_organizations_for_access(user):
    """
    Organizations where the user is a member (profile) or the owner.
    Deduplicated, member org first when present.
    """
    if not user:
        return []
    from api.authenticate.models import Organization

    orgs = []
    seen: set = set()
    user_org = get_user_organization(user)
    if user_org:
        orgs.append(user_org)
        seen.add(user_org.id)
    for org in Organization.objects.filter(owner=user):
        if org.id not in seen:
            orgs.append(org)
            seen.add(org.id)
    return orgs


def get_user_organization(user):
    """
    Safe accessor for a user's organization.

    IMPORTANT: accessing `user.profile` can raise UserProfile.DoesNotExist for legacy users,
    so we must guard it.
    """
    if not user:
        return None
    try:
        profile = getattr(user, "profile", None)
    except Exception:
        return None
    return getattr(profile, "organization", None)


def get_active_role_ids(user, organization):
    """
    Return a queryset of role IDs the user currently holds in this organization.
    """
    if not user or not organization:
        return []
    from api.authenticate.models import RoleAssignment

    today = timezone.now().date()
    return RoleAssignment.objects.filter(
        user=user,
        organization=organization,
        from_date__lte=today,
    ).filter(Q(to_date__isnull=True) | Q(to_date__gte=today)).values_list("role_id", flat=True)


def accessible_agents_qs(user):
    """
    Agents accessible to this authenticated user.

    Rules:
    - Personal agents: user owns them (Agent.user == user).
    - Organization conversational agents:
        - If no roles assigned to the agent: any org member can access.
        - If roles assigned: only users with any of those roles can access.
        - Org owner can always access.
    - Platform assistants: user's org row + platform-assistant feature flag
      (not granted to all org members via empty allowed_roles).
    """
    from api.ai_layers.models import Agent, AgentKind
    from api.authenticate.services import FeatureFlagService

    user_org = get_user_organization(user)
    orgs_for_access = get_user_organizations_for_access(user)

    qs = Agent.objects.filter(user=user)

    if user_org:
        active_role_ids = get_active_role_ids(user, user_org)
        org_q = Q(organization=user_org) & Q(agent_kind=AgentKind.CONVERSATIONAL_AGENT) & (
            Q(organization__owner=user)
            | Q(role_access_assignments__isnull=True)
            | Q(role_access_assignments__role_id__in=active_role_ids)
        )
        qs = Agent.objects.filter(Q(user=user) | org_q)

    platform_ids: set = set()
    platform_flag_debug: list[dict] = []
    for org in orgs_for_access:
        enabled, reason = FeatureFlagService.is_feature_enabled(
            "platform-assistant", organization=org, user=user
        )
        platform_flag_debug.append(
            {
                "org_id": str(org.id),
                "org_name": org.name,
                "enabled": enabled,
                "reason": reason,
            }
        )
        if enabled:
            platform_ids.add(org.id)
    if platform_ids:
        qs = qs | Agent.objects.filter(
            organization_id__in=platform_ids,
            agent_kind=AgentKind.PLATFORM_ASSISTANT,
        )

    logger.debug(
        "accessible_agents_qs user_id=%s profile_org_id=%s orgs_for_access=%s "
        "platform_flag=%s platform_ids=%s",
        getattr(user, "id", None),
        str(user_org.id) if user_org else None,
        [str(o.id) for o in orgs_for_access],
        platform_flag_debug,
        list(platform_ids),
    )

    return qs.distinct()

