from api.authenticate.models import Organization
from api.authenticate.views import _can_manage_organization


def can_manage_data_governance(user, organization: Organization) -> bool:
    return _can_manage_organization(user, organization)
