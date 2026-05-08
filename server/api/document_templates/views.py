from __future__ import annotations

import json
import uuid

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from api.ai_layers.access import accessible_agents_qs
from api.ai_layers.models import Agent
from api.authenticate.decorators.token_required import token_required
from api.authenticate.models import Organization
from api.authenticate.services import FeatureFlagService
from api.document_templates.access import user_can_manage_org_templates
from api.document_templates.models import AgentDocumentTemplateAssignment, DocumentTemplate
from api.document_templates.utils import (
    build_template_metadata,
    extract_placeholders_from_storage_file,
)


def _template_to_dict(t: DocumentTemplate) -> dict:
    return {
        "id": str(t.id),
        "organization_id": str(t.organization_id),
        "name": t.name,
        "description": t.description,
        "is_active": t.is_active,
        "original_filename": t.original_filename,
        "file_size": t.file_size,
        "content_type": t.content_type,
        "metadata": t.metadata or {},
        "file_url": t.file.url if t.file else "",
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _assignment_to_dict(a: AgentDocumentTemplateAssignment) -> dict:
    return {
        "id": str(a.id),
        "agent_id": a.agent_id,
        "agent_slug": a.agent.slug,
        "template_id": str(a.template_id),
        "template_name": a.template.name,
        "usage_instructions": a.usage_instructions,
        "is_enabled": a.is_enabled,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _get_org_or_404(request, org_id: str) -> Organization | JsonResponse:
    try:
        org = Organization.objects.get(id=org_id)
    except (Organization.DoesNotExist, ValueError):
        return JsonResponse({"error": "Organization not found"}, status=404)
    if not user_can_manage_org_templates(request.user, org):
        return JsonResponse({"error": "Forbidden"}, status=403)
    return org


def _apply_uploaded_file_and_extract(
    template: DocumentTemplate, uploaded, previous_metadata: dict | None = None
) -> None:
    name = uploaded.name or "template.docx"
    if not name.lower().endswith(".docx"):
        raise ValueError("Only .docx files are supported")
    template.original_filename = name
    template.file_size = getattr(uploaded, "size", 0) or 0
    template.content_type = getattr(uploaded, "content_type", "") or template.content_type
    template.file.save(f"{uuid.uuid4()}.docx", uploaded, save=False)
    template.metadata = build_template_metadata(
        extract_placeholders_from_storage_file(template.file),
        previous_metadata,
    )


def _can_edit_agent(request, agent: Agent) -> bool:
    user_org = None
    if hasattr(request.user, "profile") and getattr(
        request.user.profile, "organization", None
    ):
        user_org = request.user.profile.organization
    has_admin_flag, _ = FeatureFlagService.is_feature_enabled(
        "edit-organization-agent",
        organization=user_org,
        user=request.user,
    )
    if has_admin_flag and user_org:
        return agent.user_id == request.user.id or agent.organization_id == user_org.id
    return agent.user_id == request.user.id


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationDocumentTemplateListView(View):
    """GET list / POST create templates for an organization."""

    def get(self, request, org_id: str):
        org = _get_org_or_404(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        qs = DocumentTemplate.objects.filter(organization=org).order_by("-created_at")
        return JsonResponse({"templates": [_template_to_dict(t) for t in qs]})

    def post(self, request, org_id: str):
        org = _get_org_or_404(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        uploaded = request.FILES.get("file")
        if not name:
            return JsonResponse({"error": "name is required"}, status=400)
        if not uploaded:
            return JsonResponse({"error": "file is required"}, status=400)
        try:
            t = DocumentTemplate(
                organization=org,
                created_by=request.user,
                name=name,
                description=description,
            )
            _apply_uploaded_file_and_extract(t, uploaded, None)
            t.save()
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
        return JsonResponse({"template": _template_to_dict(t)}, status=201)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationDocumentTemplateDetailView(View):
    """GET / PATCH / DELETE a single template."""

    def get(self, request, org_id: str, template_id: str):
        org = _get_org_or_404(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        t = DocumentTemplate.objects.filter(organization=org, id=template_id).first()
        if not t:
            return JsonResponse({"error": "Template not found"}, status=404)
        return JsonResponse({"template": _template_to_dict(t)})

    def patch(self, request, org_id: str, template_id: str):
        org = _get_org_or_404(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        t = DocumentTemplate.objects.filter(organization=org, id=template_id).first()
        if not t:
            return JsonResponse({"error": "Template not found"}, status=404)
        uploaded = request.FILES.get("file")
        if uploaded:
            try:
                _apply_uploaded_file_and_extract(t, uploaded, t.metadata)
            except ValueError as e:
                return JsonResponse({"error": str(e)}, status=400)
        if request.content_type and "application/json" in request.content_type:
            try:
                data = json.loads(request.body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON"}, status=400)
            if "name" in data:
                t.name = str(data.get("name") or "").strip() or t.name
            if "description" in data:
                t.description = str(data.get("description") or "")
            if "is_active" in data:
                t.is_active = bool(data.get("is_active"))
        else:
            if request.POST.get("name"):
                t.name = request.POST.get("name", "").strip()
            if request.POST.get("description") is not None:
                t.description = request.POST.get("description", "").strip()
            if request.POST.get("is_active") is not None:
                t.is_active = request.POST.get("is_active", "true").lower() in (
                    "1",
                    "true",
                    "yes",
                )
        t.save()
        return JsonResponse({"template": _template_to_dict(t)})

    def delete(self, request, org_id: str, template_id: str):
        org = _get_org_or_404(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        t = DocumentTemplate.objects.filter(organization=org, id=template_id).first()
        if not t:
            return JsonResponse({"error": "Template not found"}, status=404)
        t.delete()
        return JsonResponse({"ok": True})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationDocumentTemplateVariablesView(View):
    """PATCH variable descriptions (metadata['variables']) for a template."""

    def patch(self, request, org_id: str, template_id: str):
        org = _get_org_or_404(request, org_id)
        if isinstance(org, JsonResponse):
            return org
        t = DocumentTemplate.objects.filter(organization=org, id=template_id).first()
        if not t:
            return JsonResponse({"error": "Template not found"}, status=404)
        try:
            data = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        incoming = data.get("variables")
        if not isinstance(incoming, dict):
            return JsonResponse({"error": "variables must be an object"}, status=400)
        md = dict(t.metadata or {})
        placeholders = list(md.get("placeholders") or [])
        if not isinstance(placeholders, list):
            placeholders = []
        vars_cur = md.get("variables")
        if not isinstance(vars_cur, dict):
            vars_cur = {}
        for key, spec in incoming.items():
            if key not in placeholders:
                return JsonResponse(
                    {"error": f"Unknown placeholder '{key}' — not in template"},
                    status=400,
                )
            if not isinstance(spec, dict):
                return JsonResponse(
                    {"error": f"variables['{key}'] must be an object"},
                    status=400,
                )
            cur = dict(vars_cur.get(key) or {})
            if "description" in spec:
                cur["description"] = str(spec.get("description") or "")
            if "required" in spec:
                cur["required"] = bool(spec.get("required"))
            if "example" in spec:
                cur["example"] = str(spec.get("example") or "")
            vars_cur[key] = {
                "description": cur.get("description", ""),
                "required": bool(cur.get("required", True)),
                "example": cur.get("example", ""),
            }
        md["variables"] = vars_cur
        t.metadata = md
        t.save(update_fields=["metadata", "updated_at"])
        return JsonResponse({"template": _template_to_dict(t)})


def _get_agent_for_user(request, slug: str) -> Agent | JsonResponse:
    agent = accessible_agents_qs(request.user).filter(slug=slug).first()
    if not agent:
        return JsonResponse({"error": "Agent not found"}, status=404)
    if not _can_edit_agent(request, agent):
        return JsonResponse({"error": "Forbidden"}, status=403)
    return agent


def _get_agent_for_assignment(request, slug: str) -> Agent | JsonResponse:
    """Agent must be in the user's accessible set (same as chat); no edit-agent flag."""
    agent = accessible_agents_qs(request.user).filter(slug=slug).first()
    if not agent:
        return JsonResponse({"error": "Agent not found"}, status=404)
    return agent


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class AgentDocumentTemplateAssignmentListView(View):
    """GET / POST template assignments for an agent."""

    def get(self, request, agent_slug: str):
        agent = _get_agent_for_assignment(request, agent_slug)
        if isinstance(agent, JsonResponse):
            return agent
        qs = AgentDocumentTemplateAssignment.objects.filter(agent=agent).select_related(
            "template"
        )
        return JsonResponse(
            {"assignments": [_assignment_to_dict(a) for a in qs.order_by("-created_at")]}
        )

    def post(self, request, agent_slug: str):
        agent = _get_agent_for_assignment(request, agent_slug)
        if isinstance(agent, JsonResponse):
            return agent
        try:
            data = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        tid = data.get("template_id")
        if not tid:
            return JsonResponse({"error": "template_id is required"}, status=400)
        template = DocumentTemplate.objects.filter(id=tid, is_active=True).first()
        if not template:
            return JsonResponse({"error": "Template not found"}, status=404)
        if not user_can_manage_org_templates(request.user, template.organization):
            return JsonResponse({"error": "Forbidden"}, status=403)
        if agent.organization_id and str(agent.organization_id) != str(
            template.organization_id
        ):
            return JsonResponse(
                {"error": "Template not found in organization"}, status=404
            )
        usage = str(data.get("usage_instructions") or "")
        is_enabled = bool(data.get("is_enabled", True))
        a, _created = AgentDocumentTemplateAssignment.objects.update_or_create(
            agent=agent,
            template=template,
            defaults={
                "usage_instructions": usage,
                "is_enabled": is_enabled,
                "created_by": request.user,
            },
        )
        return JsonResponse({"assignment": _assignment_to_dict(a)}, status=201)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class AgentDocumentTemplateAssignmentDetailView(View):
    """PATCH / DELETE a template assignment."""

    def patch(self, request, agent_slug: str, assignment_id: str):
        agent = _get_agent_for_assignment(request, agent_slug)
        if isinstance(agent, JsonResponse):
            return agent
        a = AgentDocumentTemplateAssignment.objects.filter(
            id=assignment_id, agent=agent
        ).first()
        if not a:
            return JsonResponse({"error": "Assignment not found"}, status=404)
        if not user_can_manage_org_templates(request.user, a.template.organization):
            return JsonResponse({"error": "Forbidden"}, status=403)
        try:
            data = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        if "usage_instructions" in data:
            a.usage_instructions = str(data.get("usage_instructions") or "")
        if "is_enabled" in data:
            a.is_enabled = bool(data.get("is_enabled"))
        a.save()
        return JsonResponse({"assignment": _assignment_to_dict(a)})

    def delete(self, request, agent_slug: str, assignment_id: str):
        agent = _get_agent_for_assignment(request, agent_slug)
        if isinstance(agent, JsonResponse):
            return agent
        a = AgentDocumentTemplateAssignment.objects.filter(
            id=assignment_id, agent=agent
        ).first()
        if not a:
            return JsonResponse({"error": "Assignment not found"}, status=404)
        if not user_can_manage_org_templates(request.user, a.template.organization):
            return JsonResponse({"error": "Forbidden"}, status=403)
        a.delete()
        return JsonResponse({"ok": True})
