from django.urls import path
from .views import (
    LoginAPIView,
    SignupAPIView,
    UserView,
    OrganizationView,
    OrganizationCredentialsView,
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
]
