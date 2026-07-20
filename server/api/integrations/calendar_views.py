"""
Google Calendar listing and event CRUD endpoints.
"""

from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from api.authenticate.decorators.token_required import token_required
from api.integrations.calendar_service import (
    create_event_for_user,
    delete_event_for_user,
    list_calendars_for_user,
    list_events_for_user,
    update_event_for_user,
)
from api.integrations.providers import IntegrationProviderError
from api.integrations.services import (
    get_user_organization,
    parse_owner_type,
    user_can_manage_integrations,
)

logger = logging.getLogger(__name__)


def _require_calendar_access(request, owner_type: str):
    org = get_user_organization(request.user)
    if not user_can_manage_integrations(request.user, org):
        return JsonResponse(
            {"error": "The 'can-manage-integrations' feature is not enabled."},
            status=403,
        )
    if owner_type == "organization" and org is None:
        return JsonResponse({"error": "User has no organization."}, status=400)
    return None


def _parse_json_body(request) -> dict | JsonResponse:
    try:
        return json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)


@csrf_exempt
@token_required
def google_calendar_list_calendars(request):
    """
    GET /v1/integrations/google_calendar/calendars/?owner=user|organization
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        owner_type = parse_owner_type(request.GET.get("owner"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    err = _require_calendar_access(request, owner_type)
    if err:
        return err

    org = get_user_organization(request.user)
    try:
        calendars = list_calendars_for_user(
            user=request.user,
            owner_type=owner_type,
            organization=org,
        )
    except IntegrationProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"calendars": calendars, "owner_type": owner_type})


@csrf_exempt
@token_required
def google_calendar_events_collection(request):
    """
    GET  /v1/integrations/google_calendar/events/ — list events
    POST /v1/integrations/google_calendar/events/ — create event
    """
    if request.method == "GET":
        return _google_calendar_list_events(request)
    if request.method == "POST":
        return _google_calendar_create_event(request)
    return JsonResponse({"error": "Method not allowed"}, status=405)


def _google_calendar_list_events(request):
    try:
        owner_type = parse_owner_type(request.GET.get("owner"))
        max_results = int(request.GET.get("max_results", "50"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    calendar_id = (request.GET.get("calendar_id") or "primary").strip()
    time_min = (request.GET.get("time_min") or "").strip() or None
    time_max = (request.GET.get("time_max") or "").strip() or None

    err = _require_calendar_access(request, owner_type)
    if err:
        return err

    org = get_user_organization(request.user)
    try:
        events = list_events_for_user(
            user=request.user,
            owner_type=owner_type,
            organization=org,
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            max_results=max_results,
        )
    except IntegrationProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        {"events": events, "owner_type": owner_type, "calendar_id": calendar_id}
    )


def _google_calendar_create_event(request):
    body = _parse_json_body(request)
    if isinstance(body, JsonResponse):
        return body

    try:
        owner_type = parse_owner_type(body.get("owner"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    calendar_id = (body.get("calendar_id") or "primary").strip()

    err = _require_calendar_access(request, owner_type)
    if err:
        return err

    org = get_user_organization(request.user)
    try:
        event = create_event_for_user(
            user=request.user,
            owner_type=owner_type,
            organization=org,
            calendar_id=calendar_id,
            payload=body,
        )
    except IntegrationProviderError as exc:
        logger.error("Calendar create event failed: %s", exc)
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"event": event}, status=201)


@csrf_exempt
@token_required
def google_calendar_event_detail(request, event_id: str):
    """
    PATCH / DELETE /v1/integrations/google_calendar/events/<event_id>/
    """
    if request.method not in ("PATCH", "DELETE"):
        return JsonResponse({"error": "Method not allowed"}, status=405)

    body: dict = {}
    if request.body:
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

    try:
        owner_type = parse_owner_type(body.get("owner") or request.GET.get("owner"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    calendar_id = (
        body.get("calendar_id") or request.GET.get("calendar_id") or "primary"
    ).strip()

    err = _require_calendar_access(request, owner_type)
    if err:
        return err

    org = get_user_organization(request.user)

    if request.method == "DELETE":
        try:
            delete_event_for_user(
                user=request.user,
                owner_type=owner_type,
                organization=org,
                calendar_id=calendar_id,
                event_id=event_id,
            )
        except IntegrationProviderError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        return JsonResponse({"success": True, "deleted": True})

    try:
        event = update_event_for_user(
            user=request.user,
            owner_type=owner_type,
            organization=org,
            calendar_id=calendar_id,
            event_id=event_id,
            payload=body,
        )
    except IntegrationProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"event": event})
