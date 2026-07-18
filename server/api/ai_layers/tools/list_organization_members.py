"""
Tool: list_organization_members

Lists members of the conversation organization for send_email recipient selection.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.authenticate.models import Organization, UserProfile
from api.authenticate.org_membership import (
    active_role_assignments_for_org,
    iter_organization_member_users,
)


class ListOrganizationMembersParams(BaseModel):
    pass


class MemberRoleSummary(BaseModel):
    role_id: str
    role_name: str


class OrganizationMemberSummary(BaseModel):
    user_id: int
    email: str
    display_name: str
    is_owner: bool
    is_active: bool
    roles: list[MemberRoleSummary] = Field(default_factory=list)
    member_since: str
    is_current_user: bool


class ListOrganizationMembersResult(BaseModel):
    members: list[OrganizationMemberSummary] = Field(default_factory=list)


def _member_since_iso(user, profile: UserProfile | None, is_owner: bool) -> str:
    if is_owner:
        return user.date_joined.isoformat()
    if profile and profile.created_at:
        return profile.created_at.isoformat()
    return user.date_joined.isoformat()


def _list_organization_members_impl(
    organization_id: int,
    current_user_id: int | None,
) -> ListOrganizationMembersResult:
    organization = Organization.objects.filter(pk=organization_id).first()
    if not organization:
        raise ValueError("Organization not found")

    roles_by_user: dict[int, list[MemberRoleSummary]] = {}
    for assignment in active_role_assignments_for_org(organization):
        roles_by_user.setdefault(assignment.user_id, []).append(
            MemberRoleSummary(
                role_id=str(assignment.role_id),
                role_name=assignment.role.name,
            )
        )

    profiles = {
        p.user_id: p
        for p in UserProfile.objects.filter(organization=organization).select_related(
            "user"
        )
    }

    members: list[OrganizationMemberSummary] = []
    for user in iter_organization_member_users(organization):
        profile = profiles.get(user.id)
        is_owner = organization.owner_id == user.id
        is_active = True if is_owner else bool(profile.is_active if profile else True)
        display_name = ""
        if profile and (profile.name or "").strip():
            display_name = profile.name.strip()
        elif user.username:
            display_name = user.username

        members.append(
            OrganizationMemberSummary(
                user_id=user.id,
                email=user.email or "",
                display_name=display_name,
                is_owner=is_owner,
                is_active=is_active,
                roles=roles_by_user.get(user.id, []),
                member_since=_member_since_iso(user, profile, is_owner),
                is_current_user=current_user_id is not None and user.id == current_user_id,
            )
        )

    members.sort(key=lambda m: (not m.is_owner, m.display_name.lower(), m.user_id))
    return ListOrganizationMembersResult(members=members)


def get_tool(
    organization_id: int | None = None,
    user_id: int | None = None,
    **kwargs,
) -> dict:
    if organization_id is None:
        raise ValueError(
            "list_organization_members requires organization_id in tool context"
        )

    def list_organization_members() -> ListOrganizationMembersResult:
        return _list_organization_members_impl(organization_id, user_id)

    return {
        "name": "list_organization_members",
        "description": (
            "List members of the current organization with user_id, email, display_name, "
            "roles, member_since, and is_current_user (true for the person chatting). "
            "Use before send_email to pick type=user recipients. "
            "For role-wide or org-wide sends, use list_organization_roles or "
            "send_email with type=organization."
        ),
        "parameters": ListOrganizationMembersParams,
        "function": list_organization_members,
    }
