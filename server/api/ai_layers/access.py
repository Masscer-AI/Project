from __future__ import annotations

from django.db.models import Q
from django.utils import timezone


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
    - Organization agents:
        - If no roles assigned to the agent: any org member can access.
        - If roles assigned: only users with any of those roles can access.
        - Org owner can always access.
    """
    from api.ai_layers.models import Agent

    user_org = get_user_organization(user)
    qs = Agent.objects.filter(user=user)
    if not user_org:
        return qs

    active_role_ids = get_active_role_ids(user, user_org)
    org_q = Q(organization=user_org) & (
        Q(organization__owner=user)
        | Q(role_access_assignments__isnull=True)
        | Q(role_access_assignments__role_id__in=active_role_ids)
    )
    return Agent.objects.filter(Q(user=user) | org_q).distinct()

