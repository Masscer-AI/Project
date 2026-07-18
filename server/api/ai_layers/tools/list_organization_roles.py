"""
Tool: list_organization_roles

Lists roles in the conversation organization for send_email recipient selection.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.authenticate.models import Organization, Role
from api.authenticate.org_membership import active_role_assignments_for_org


class ListOrganizationRolesParams(BaseModel):
    pass


class OrganizationRoleSummary(BaseModel):
    role_id: str
    name: str
    description: str | None = None
    active_member_count: int = 0
    member_user_ids: list[int] = Field(default_factory=list)


class ListOrganizationRolesResult(BaseModel):
    roles: list[OrganizationRoleSummary] = Field(default_factory=list)


def _list_organization_roles_impl(organization_id: int) -> ListOrganizationRolesResult:
    organization = Organization.objects.filter(pk=organization_id).first()
    if not organization:
        raise ValueError("Organization not found")

    members_by_role: dict[str, set[int]] = {}
    for assignment in active_role_assignments_for_org(organization):
        role_key = str(assignment.role_id)
        members_by_role.setdefault(role_key, set()).add(assignment.user_id)

    roles: list[OrganizationRoleSummary] = []
    for role in Role.objects.filter(organization=organization, enabled=True).order_by(
        "name"
    ):
        member_ids = sorted(members_by_role.get(str(role.id), set()))
        roles.append(
            OrganizationRoleSummary(
                role_id=str(role.id),
                name=role.name,
                description=role.description,
                active_member_count=len(member_ids),
                member_user_ids=member_ids,
            )
        )

    return ListOrganizationRolesResult(roles=roles)


def get_tool(organization_id: int | None = None, **kwargs) -> dict:
    if organization_id is None:
        raise ValueError(
            "list_organization_roles requires organization_id in tool context"
        )

    def list_organization_roles() -> ListOrganizationRolesResult:
        return _list_organization_roles_impl(organization_id)

    return {
        "name": "list_organization_roles",
        "description": (
            "List enabled roles in the current organization with role_id, name, "
            "active_member_count, and member_user_ids. "
            "Use before send_email to target type=role recipients."
        ),
        "parameters": ListOrganizationRolesParams,
        "function": list_organization_roles,
    }
