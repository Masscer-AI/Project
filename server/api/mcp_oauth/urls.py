from django.urls import path

from api.mcp_oauth import views

app_name = "mcp_oauth"

urlpatterns = [
    path(
        "authorize-request/<uuid:request_id>/",
        views.authorize_request_detail,
        name="oauth_authorize_request_detail",
    ),
    path(
        "authorize-request/<uuid:request_id>/approve/",
        views.authorize_request_approve,
        name="oauth_authorize_request_approve",
    ),
    path(
        "authorize-request/<uuid:request_id>/deny/",
        views.authorize_request_deny,
        name="oauth_authorize_request_deny",
    ),
    path("introspect/", views.token_introspect, name="oauth_token_introspect"),
    path("clients/", views.oauth_clients, name="oauth_clients"),
    path("clients/<uuid:client_id>/", views.oauth_client_detail, name="oauth_client_detail"),
]
