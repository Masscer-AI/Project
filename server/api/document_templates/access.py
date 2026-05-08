from __future__ import annotations

from django.contrib.auth.models import User

from api.authenticate.models import Organization, UserProfile


def user_belongs_to_organization(user: User, organization: Organization) -> bool:
    if not user or not organization:
        return False
    if organization.owner_id == user.id:
        return True
    return UserProfile.objects.filter(user=user, organization=organization).exists()


def user_can_manage_org_templates(user: User, organization: Organization) -> bool:
    """Owner or org member may manage templates (same baseline as belonging)."""
    return user_belongs_to_organization(user, organization)
