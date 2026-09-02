from django.urls import path

from api.compliance.views import (
    MyPLDExpedientView,
    PLDEntityDetailView,
    PLDEntityInviteView,
    PLDEntityListView,
    PLDInviteAcceptView,
    PLDInvitePublicView,
)

app_name = "compliance"

urlpatterns = [
    path("entities/", PLDEntityListView.as_view(), name="pld_entity_list"),
    path(
        "entities/<uuid:entity_id>/",
        PLDEntityDetailView.as_view(),
        name="pld_entity_detail",
    ),
    path(
        "entities/<uuid:entity_id>/invite/",
        PLDEntityInviteView.as_view(),
        name="pld_entity_invite",
    ),
    path("invites/public/", PLDInvitePublicView.as_view(), name="pld_invite_public"),
    path("invites/accept/", PLDInviteAcceptView.as_view(), name="pld_invite_accept"),
    path("my-expedients/", MyPLDExpedientView.as_view(), name="my_pld_expedients"),
]
