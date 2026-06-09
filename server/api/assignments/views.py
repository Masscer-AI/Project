from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status

from api.authenticate.decorators.token_required import token_required
from api.assignments.models import AssignmentStatus, UserAssignment
from api.assignments.serializers import serialize_assignment
from api.assignments.services import archive_assignment, update_assignment_step_status


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class UserAssignmentListView(View):
    def get(self, request):
        qs = UserAssignment.objects.filter(user=request.user)
        status_filter = request.GET.get("status")
        key_filter = request.GET.get("key")

        if status_filter:
            qs = qs.filter(status=status_filter)
        else:
            qs = qs.exclude(status=AssignmentStatus.ARCHIVED)

        if key_filter:
            qs = qs.filter(key=key_filter)

        data = [serialize_assignment(a) for a in qs]
        return JsonResponse({"assignments": data}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class UserAssignmentDetailView(View):
    def get(self, request, assignment_id):
        assignment = get_object_or_404(
            UserAssignment, id=assignment_id, user=request.user
        )
        return JsonResponse(serialize_assignment(assignment), status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class UserAssignmentStepView(View):
    def patch(self, request, assignment_id, step_id):
        assignment = get_object_or_404(
            UserAssignment, id=assignment_id, user=request.user
        )
        try:
            body = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        new_status = body.get("status")
        if not new_status:
            return JsonResponse({"error": "status is required"}, status=400)

        try:
            update_assignment_step_status(assignment, step_id, new_status)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        assignment.refresh_from_db()
        return JsonResponse(serialize_assignment(assignment), status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class UserAssignmentArchiveView(View):
    def post(self, request, assignment_id):
        assignment = get_object_or_404(
            UserAssignment, id=assignment_id, user=request.user
        )
        archive_assignment(assignment)
        assignment.refresh_from_db()
        return JsonResponse(serialize_assignment(assignment), status=status.HTTP_200_OK)
