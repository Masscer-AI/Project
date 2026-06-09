from django.urls import path

from api.assignments.views import (
    UserAssignmentArchiveView,
    UserAssignmentDetailView,
    UserAssignmentListView,
    UserAssignmentStepView,
)

app_name = "assignments"

urlpatterns = [
    path("", UserAssignmentListView.as_view(), name="assignments_list"),
    path("<uuid:assignment_id>/", UserAssignmentDetailView.as_view(), name="assignments_detail"),
    path(
        "<uuid:assignment_id>/steps/<str:step_id>/",
        UserAssignmentStepView.as_view(),
        name="assignments_step_update",
    ),
    path(
        "<uuid:assignment_id>/archive/",
        UserAssignmentArchiveView.as_view(),
        name="assignments_archive",
    ),
]
