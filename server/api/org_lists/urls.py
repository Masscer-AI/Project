from django.urls import path

from api.org_lists import views

app_name = "org_lists"

urlpatterns = [
    path(
        "organizations/<uuid:org_id>/lists/",
        views.OrganizationListCollectionView.as_view(),
        name="org_list_collection",
    ),
    path(
        "organizations/<uuid:org_id>/lists/<uuid:list_id>/",
        views.OrganizationListDetailView.as_view(),
        name="org_list_detail",
    ),
    path(
        "organizations/<uuid:org_id>/lists/<uuid:list_id>/file/",
        views.OrganizationListFileView.as_view(),
        name="org_list_file",
    ),
    path(
        "organizations/<uuid:org_id>/lists/<uuid:list_id>/records/",
        views.OrganizationListRecordsView.as_view(),
        name="org_list_records",
    ),
]
