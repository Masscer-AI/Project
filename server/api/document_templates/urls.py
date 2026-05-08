from django.urls import path

from api.document_templates import views

app_name = "document_templates"

urlpatterns = [
    path(
        "organizations/<uuid:org_id>/templates/",
        views.OrganizationDocumentTemplateListView.as_view(),
        name="org_template_list",
    ),
    path(
        "organizations/<uuid:org_id>/templates/<uuid:template_id>/",
        views.OrganizationDocumentTemplateDetailView.as_view(),
        name="org_template_detail",
    ),
    path(
        "organizations/<uuid:org_id>/templates/<uuid:template_id>/variables/",
        views.OrganizationDocumentTemplateVariablesView.as_view(),
        name="org_template_variables",
    ),
    path(
        "agents/<slug:agent_slug>/template-assignments/",
        views.AgentDocumentTemplateAssignmentListView.as_view(),
        name="agent_template_assignments",
    ),
    path(
        "agents/<slug:agent_slug>/template-assignments/<uuid:assignment_id>/",
        views.AgentDocumentTemplateAssignmentDetailView.as_view(),
        name="agent_template_assignment_detail",
    ),
]
