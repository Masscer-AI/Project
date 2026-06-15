from django.urls import path

from api.data_governance.views import (
    DataExportJobDetailView,
    DataExportJobDownloadView,
    DataExportJobListCreateView,
    OrganizationDataPolicyView,
)

app_name = "data_governance"

urlpatterns = [
    path(
        "organizations/<uuid:organization_id>/policy/",
        OrganizationDataPolicyView.as_view(),
        name="organization_policy",
    ),
    path(
        "organizations/<uuid:organization_id>/exports/",
        DataExportJobListCreateView.as_view(),
        name="export_list_create",
    ),
    path(
        "organizations/<uuid:organization_id>/exports/<uuid:job_id>/",
        DataExportJobDetailView.as_view(),
        name="export_detail",
    ),
    path(
        "organizations/<uuid:organization_id>/exports/<uuid:job_id>/download/",
        DataExportJobDownloadView.as_view(),
        name="export_download",
    ),
]
