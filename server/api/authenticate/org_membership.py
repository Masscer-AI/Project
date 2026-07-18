"""
Organization membership helpers for agent tools (email, member lists).

Semantics align with notification target resolution: owner + active profiles
+ users with active role assignments.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from api.authenticate.models import Organization, Role, RoleAssignment, UserProfile


def _active_assignment_qs(organization: Organization):
    today = timezone.now().date()
    return RoleAssignment.objects.filter(
        organization=organization,
        from_date__lte=today,
    ).filter(Q(to_date__isnull=True) | Q(to_date__gte=today))


def iter_organization_member_users(organization: Organization) -> list[User]:
    """Owner + active UserProfile members + users with active role assignments."""
    user_ids: set[int] = set()

    if organization.owner_id:
        user_ids.add(organization.owner_id)

    user_ids.update(
        UserProfile.objects.filter(
            organization=organization,
            is_active=True,
        ).values_list("user_id", flat=True)
    )

    user_ids.update(
        _active_assignment_qs(organization).values_list("user_id", flat=True)
    )

    if not user_ids:
        return []

    return list(User.objects.filter(id__in=user_ids).order_by("id"))


def user_belongs_to_organization(user: User, organization: Organization) -> bool:
    member_ids = {u.id for u in iter_organization_member_users(organization)}
    return user.id in member_ids


def users_with_role(organization_id: int, role_id: str) -> list[User]:
    role = Role.objects.filter(
        id=role_id,
        organization_id=organization_id,
        enabled=True,
    ).first()
    if not role:
        raise ValueError(f"Role {role_id} not found in this organization")

    qs = _active_assignment_qs(role.organization).filter(role_id=role.id)
    return list({ra.user for ra in qs.select_related("user")})


def active_role_assignments_for_org(organization: Organization):
    return _active_assignment_qs(organization).select_related("role", "user")
