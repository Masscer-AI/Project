from __future__ import annotations


def get_pld_organization_for_user(user):
    """First org the user can access that has PLD enabled."""
    from api.ai_layers.access import get_user_organizations_for_access

    if not user:
        return None
    for org in get_user_organizations_for_access(user):
        if getattr(org, "pld_access_enabled", False):
            return org
    return None
