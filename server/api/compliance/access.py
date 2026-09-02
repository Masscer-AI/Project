from __future__ import annotations

ORGANIZATION_COMPLIANCE_ACCESS_FLAG = "organization-compliance-access"


def user_has_organization_compliance_access(user, organization=None) -> bool:
    from api.authenticate.services import FeatureFlagService

    if not user:
        return False
    enabled, _ = FeatureFlagService.is_feature_enabled(
        ORGANIZATION_COMPLIANCE_ACCESS_FLAG,
        organization=organization,
        user=user,
    )
    return enabled


def get_pld_organization_for_user(user):
    """First org the user can access that has PLD enabled and the compliance flag."""
    from api.ai_layers.access import get_user_organizations_for_access

    if not user:
        return None
    for org in get_user_organizations_for_access(user):
        if not getattr(org, "pld_access_enabled", False):
            continue
        if user_has_organization_compliance_access(user, org):
            return org
    return None
