from django.urls import path
from .views import LoginAPIView, SignupAPIView, UserView, OrganizationView

app_name = "authenticate"

urlpatterns = [
    path("signup", SignupAPIView.as_view(), name="api_signup"),
    path("login", LoginAPIView.as_view(), name="api_login"),
    path("user/me", UserView.as_view(), name="user_me"),
    path("organizations/", OrganizationView.as_view(), name="organization"),
]
