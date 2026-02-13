from django.urls import path
from .views import (
    LoginAPIView,
    SignupAPIView,
    UserView,
    OrganizationView,
    OrganizationCredentialsView,
    OrganizationMembersView,
    OrganizationMemberDetailView,
    OrganizationRolesView,
    OrganizationRoleDetailView,
    OrganizationRoleAssignmentsView,
    FeatureFlagNamesView,
    FeatureFlagCheckView,
    FeatureFlagListView,
)

app_name = "authenticate"

urlpatterns = [
    path("signup", SignupAPIView.as_view(), name="api_signup"),
    path("login", LoginAPIView.as_view(), name="api_login"),
    path("user/me", UserView.as_view(), name="user_me"),
    path("organizations/", OrganizationView.as_view(), name="organization"),
    path(
        "organizations/<str:organization_id>/",
        OrganizationView.as_view(),
        name="organization_id",
    ),
    path(
        "organizations/<str:organization_id>/credentials/",
        OrganizationCredentialsView.as_view(),
        name="organization_credentials",
    ),
    path(
        "organizations/<str:organization_id>/members/",
        OrganizationMembersView.as_view(),
        name="organization_members",
    ),
    path(
        "organizations/<str:organization_id>/members/<int:user_id>/",
        OrganizationMemberDetailView.as_view(),
        name="organization_member_detail",
    ),
    path(
        "organizations/<str:organization_id>/roles/",
        OrganizationRolesView.as_view(),
        name="organization_roles",
    ),
    path(
        "organizations/<str:organization_id>/roles/<uuid:role_id>/",
        OrganizationRoleDetailView.as_view(),
        name="organization_role_detail",
    ),
    path(
        "organizations/<str:organization_id>/roles/assignments/",
        OrganizationRoleAssignmentsView.as_view(),
        name="organization_role_assignments",
    ),
    path(
        "feature-flags/names/",
        FeatureFlagNamesView.as_view(),
        name="feature_flag_names",
    ),
    path(
        "feature-flags/<str:feature_flag_name>/check",
        FeatureFlagCheckView.as_view(),
        name="feature_flag_check",
    ),
    path(
        "feature-flags/",
        FeatureFlagListView.as_view(),
        name="feature_flag_list",
    ),
]
