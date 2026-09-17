from __future__ import annotations

from django.contrib.auth.models import User

from api.authenticate.models import Organization
from api.document_templates.access import user_belongs_to_organization
from api.rag.access import user_has_train_agents


def user_can_manage_org_lists(user: User, organization: Organization) -> bool:
    if not user or not organization:
        return False
    if not user_belongs_to_organization(user, organization):
        return False
    return user_has_train_agents(user)
