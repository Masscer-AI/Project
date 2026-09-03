from __future__ import annotations

import json

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from api.authenticate.decorators.token_required import token_required
from api.compliance.access import get_pld_organization_for_user
from api.compliance.invites import (
    accept_pld_invite,
    create_or_rotate_pending_invite,
    entity_display_name,
    latest_invite_payload,
    public_invite_payload,
    register_user_from_pld_invite,
    send_pld_invite_email,
)
from api.compliance.models import (
    PLDEntity,
    PLDExpedient,
    PLDExpedientDocument,
    PLDExpedientStatus,
    PLDInvite,
    PLDPersonType,
    PLDRelationship,
)


def _frontend_base_url(request):
    from django.conf import settings

    frontend_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    if not frontend_url:
        scheme = "https" if request.is_secure() else "http"
        frontend_url = f"{scheme}://{request.get_host()}"
    return frontend_url


def _entity_payload(entity: PLDEntity) -> dict:
    expedient = entity.expedients.order_by("created_at").first()
    return {
        "id": str(entity.id),
        "person_type": entity.person_type,
        "relationship": entity.relationship,
        "email": entity.email or "",
        "metadata": entity.metadata or {},
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        "invite": latest_invite_payload(entity),
        "expedient": (
            {
                "id": str(expedient.id),
                "status": expedient.status,
                "vulnerable_activity": expedient.vulnerable_activity,
            }
            if expedient
            else None
        ),
    }


def _parse_json_body(request):
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Invalid JSON body"}, status=400)
    if not isinstance(payload, dict):
        return None, JsonResponse({"error": "Invalid JSON body"}, status=400)
    return payload, None


def _org_or_404(request):
    org = get_pld_organization_for_user(request.user)
    if org is None:
        return None, JsonResponse(
            {"error": "PLD is not enabled for this organization"},
            status=404,
        )
    return org, None


def _counterparty_or_404(org, entity_id):
    try:
        entity = PLDEntity.objects.prefetch_related("expedients", "invites").get(
            pk=entity_id,
            organization=org,
        )
    except (PLDEntity.DoesNotExist, ValidationError, ValueError):
        return None, JsonResponse({"error": "Entity not found"}, status=404)
    if entity.relationship is None:
        return None, JsonResponse(
            {"error": "The organization entity cannot be changed here"},
            status=400,
        )
    return entity, None


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class PLDEntityListView(View):
    """List and create PLD counterparties for the user's PLD-enabled organization."""

    def get(self, request, *args, **kwargs):
        org, err = _org_or_404(request)
        if err:
            return err
        entities = (
            PLDEntity.objects.filter(organization=org)
            .prefetch_related("expedients", "invites")
            .order_by("-updated_at")
        )
        return JsonResponse(
            {"results": [_entity_payload(entity) for entity in entities]},
            status=200,
        )

    def post(self, request, *args, **kwargs):
        org, err = _org_or_404(request)
        if err:
            return err
        payload, err = _parse_json_body(request)
        if err:
            return err

        person_type = payload.get("person_type")
        relationship = payload.get("relationship")
        metadata = payload.get("metadata") or {}
        email = str(payload.get("email") or "").strip().lower()
        if person_type not in PLDPersonType.values:
            return JsonResponse({"error": "Invalid person_type"}, status=400)
        if relationship not in PLDRelationship.values:
            return JsonResponse(
                {"error": "relationship is required (cliente, proveedor, or ambos)"},
                status=400,
            )
        if not isinstance(metadata, dict):
            return JsonResponse({"error": "metadata must be an object"}, status=400)
        if not email:
            return JsonResponse({"error": "email is required"}, status=400)
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({"error": "Invalid email"}, status=400)

        try:
            with transaction.atomic():
                entity = PLDEntity(
                    organization=org,
                    person_type=person_type,
                    relationship=relationship,
                    email=email,
                    metadata=metadata,
                )
                entity.save()
                PLDExpedient.objects.get_or_create(
                    organization=org,
                    entity=entity,
                    defaults={"status": PLDExpedientStatus.DATA_COLLECTION},
                )
        except ValidationError as exc:
            return JsonResponse(
                {"error": getattr(exc, "message_dict", None) or str(exc)},
                status=400,
            )

        entity = PLDEntity.objects.prefetch_related("expedients", "invites").get(
            pk=entity.pk
        )
        return JsonResponse(_entity_payload(entity), status=201)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class PLDEntityDetailView(View):
    def delete(self, request, entity_id, *args, **kwargs):
        org, err = _org_or_404(request)
        if err:
            return err
        entity, err = _counterparty_or_404(org, entity_id)
        if err:
            return err
        entity.delete()
        return JsonResponse({"ok": True}, status=200)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class PLDEntityInviteView(View):
    def post(self, request, entity_id, *args, **kwargs):
        org, err = _org_or_404(request)
        if err:
            return err
        entity, err = _counterparty_or_404(org, entity_id)
        if err:
            return err
        if not (entity.email or "").strip():
            return JsonResponse({"error": "email is required"}, status=400)

        try:
            invite, raw_token = create_or_rotate_pending_invite(
                entity=entity,
                invited_by=request.user,
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        signup_url = f"{_frontend_base_url(request)}/signup?pld_invite={raw_token}"
        try:
            send_pld_invite_email(
                invite_email=invite.email,
                organization_name=org.name,
                signup_url=signup_url,
            )
        except Exception:
            return JsonResponse({"error": "Failed to send invite email"}, status=500)

        entity = PLDEntity.objects.prefetch_related("expedients", "invites").get(
            pk=entity.pk
        )
        return JsonResponse(_entity_payload(entity), status=200)


@method_decorator(csrf_exempt, name="dispatch")
class PLDInvitePublicView(View):
    """Unauthenticated lookup for /signup?pld_invite= and existing-user accept."""

    def get(self, request, *args, **kwargs):
        raw = (request.GET.get("token") or "").strip()
        invite = PLDInvite.lookup_by_raw_token(raw)
        if not invite:
            return JsonResponse(
                {"invite_valid": False, "error": "invalid-or-expired-invite"},
                status=400,
            )
        payload = public_invite_payload(invite)
        status_code = 200 if payload.get("invite_valid") or payload.get(
            "email_already_registered"
        ) else 400
        return JsonResponse(payload, status=status_code)

    def post(self, request, *args, **kwargs):
        payload, err = _parse_json_body(request)
        if err:
            return err
        raw = str(payload.get("token") or "").strip()
        password = payload.get("password") or ""
        confirm = payload.get("confirm_password") or ""
        if not password or len(password) < 8:
            return JsonResponse({"error": "password-too-short"}, status=400)
        if password != confirm:
            return JsonResponse({"error": "passwords-do-not-match"}, status=400)

        invite = PLDInvite.lookup_by_raw_token(raw)
        if not invite:
            return JsonResponse({"error": "invalid-or-expired-invite"}, status=400)
        invite.mark_expired_if_needed()
        invite.refresh_from_db()
        if invite.status != PLDInvite.Status.PENDING or invite.is_invite_expired():
            return JsonResponse({"error": "invalid-or-expired-invite"}, status=400)
        if User.objects.filter(email__iexact=invite.email).exists():
            return JsonResponse({"error": "email-already-registered"}, status=400)

        from django.contrib.auth.password_validation import validate_password

        try:
            validate_password(password)
        except ValidationError as exc:
            return JsonResponse({"error": list(exc.messages)}, status=400)

        with transaction.atomic():
            locked = PLDInvite.objects.select_for_update().select_related("entity").get(
                pk=invite.pk
            )
            if locked.status != PLDInvite.Status.PENDING:
                return JsonResponse({"error": "invalid-or-expired-invite"}, status=400)
            user = register_user_from_pld_invite(locked, password)
            accept_pld_invite(invite=locked, user=user)

        return JsonResponse({"message": "User created successfully"}, status=201)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class PLDInviteAcceptView(View):
    def post(self, request, *args, **kwargs):
        payload, err = _parse_json_body(request)
        if err:
            return err
        raw = str(payload.get("token") or "").strip()
        invite = PLDInvite.lookup_by_raw_token(raw)
        if not invite:
            return JsonResponse({"error": "invalid-or-expired-invite"}, status=400)
        invite.mark_expired_if_needed()
        invite.refresh_from_db()
        if invite.status != PLDInvite.Status.PENDING or invite.is_invite_expired():
            return JsonResponse({"error": "invalid-or-expired-invite"}, status=400)
        try:
            with transaction.atomic():
                locked = PLDInvite.objects.select_for_update().select_related(
                    "entity"
                ).get(pk=invite.pk)
                if locked.status != PLDInvite.Status.PENDING:
                    return JsonResponse(
                        {"error": "invalid-or-expired-invite"}, status=400
                    )
                accept_pld_invite(invite=locked, user=request.user)
        except ValueError:
            return JsonResponse({"error": "email-mismatch"}, status=403)
        return JsonResponse({"ok": True}, status=200)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class MyPLDExpedientView(View):
    def get(self, request, *args, **kwargs):
        entities = (
            PLDEntity.objects.filter(user=request.user)
            .exclude(relationship__isnull=True)
            .select_related("organization")
            .prefetch_related("expedients", "expedients__documents")
            .order_by("-updated_at")
        )
        return JsonResponse(
            {
                "results": [
                    _my_expedient_row(entity) for entity in entities
                ]
            },
            status=200,
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class MyPLDExpedientDetailView(View):
    """Invitee updates identification data on their own counterparty entity."""

    def patch(self, request, entity_id, *args, **kwargs):
        from api.compliance.pld_metadata import normalize_pld_entity_metadata

        try:
            entity = PLDEntity.objects.select_related("organization").get(
                pk=entity_id,
                user=request.user,
            )
        except (PLDEntity.DoesNotExist, ValidationError, ValueError):
            return JsonResponse({"error": "Entity not found"}, status=404)
        if entity.relationship is None:
            return JsonResponse({"error": "Entity not found"}, status=404)

        payload, err = _parse_json_body(request)
        if err:
            return err
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            return JsonResponse({"error": "metadata must be an object"}, status=400)
        try:
            entity.metadata = normalize_pld_entity_metadata(
                entity.person_type, metadata
            )
            entity.save(update_fields=["metadata", "updated_at"])
        except ValidationError as exc:
            return JsonResponse(
                {"error": getattr(exc, "message_dict", None) or str(exc)},
                status=400,
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        _advance_expedient_to_document_collection(entity)
        return JsonResponse(_reload_my_expedient_row(entity.pk), status=200)


def _my_expedient_row(entity: PLDEntity) -> dict:
    from api.compliance.pld_document_slots import document_slots_for_entity

    exp = entity.expedients.order_by("created_at").first()
    uploaded = {}
    if exp:
        for doc in exp.documents.all():
            uploaded[doc.slot_key] = _document_payload(doc)
    slots = []
    for slot in document_slots_for_entity(entity):
        slots.append({**slot, "document": uploaded.get(slot["slot_key"])})
    return {
        "id": str(entity.id),
        "name": entity_display_name(entity),
        "organization_name": entity.organization.name,
        "person_type": entity.person_type,
        "relationship": entity.relationship,
        "email": entity.email or "",
        "metadata": entity.metadata if isinstance(entity.metadata, dict) else {},
        "expedient": (
            {"id": str(exp.id), "status": exp.status} if exp else None
        ),
        "document_slots": slots,
    }


def _reload_my_expedient_row(entity_id) -> dict:
    entity = (
        PLDEntity.objects.select_related("organization")
        .prefetch_related("expedients", "expedients__documents")
        .get(pk=entity_id)
    )
    return _my_expedient_row(entity)


def _document_payload(doc: PLDExpedientDocument) -> dict:
    return {
        "id": str(doc.id),
        "slot_key": doc.slot_key,
        "document_kind": doc.document_kind,
        "original_filename": doc.original_filename,
        "content_type": doc.content_type,
        "file_size": doc.file_size,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def _advance_expedient_to_document_collection(entity: PLDEntity) -> None:
    exp = entity.expedients.order_by("created_at").first()
    if not exp or exp.status != PLDExpedientStatus.DATA_COLLECTION:
        return
    exp.status = PLDExpedientStatus.DOCUMENT_COLLECTION
    exp.save(update_fields=["status", "updated_at"])


def _invitee_counterparty_or_404(request, entity_id):
    try:
        entity = (
            PLDEntity.objects.select_related("organization")
            .prefetch_related("expedients", "expedients__documents")
            .get(pk=entity_id, user=request.user)
        )
    except (PLDEntity.DoesNotExist, ValidationError, ValueError):
        return None, JsonResponse({"error": "Entity not found"}, status=404)
    if entity.relationship is None:
        return None, JsonResponse({"error": "Entity not found"}, status=404)
    return entity, None


MAX_PLD_DOCUMENT_BYTES = 10 * 1024 * 1024
_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class MyPLDExpedientDocumentView(View):
    """Invitee uploads or replaces a file for one checklist slot."""

    def post(self, request, entity_id, *args, **kwargs):
        import os

        entity, err = _invitee_counterparty_or_404(request, entity_id)
        if err:
            return err
        exp = entity.expedients.order_by("created_at").first()
        if not exp:
            return JsonResponse({"error": "Expedient not found"}, status=404)
        if exp.status == PLDExpedientStatus.DATA_COLLECTION:
            return JsonResponse(
                {"error": "save-identification-first"},
                status=400,
            )

        slot_key = (request.POST.get("slot_key") or "").strip()
        uploaded = request.FILES.get("file")
        if not slot_key:
            return JsonResponse({"error": "slot_key is required"}, status=400)
        if not uploaded:
            return JsonResponse({"error": "file is required"}, status=400)

        from api.compliance.pld_document_slots import document_slots_for_entity

        slot = next(
            (
                item
                for item in document_slots_for_entity(entity)
                if item["slot_key"] == slot_key
            ),
            None,
        )
        if not slot:
            return JsonResponse({"error": "unknown-slot"}, status=400)

        filename = uploaded.name or "document"
        ext = os.path.splitext(filename)[1].lower()
        content_type = (getattr(uploaded, "content_type", "") or "").lower()
        if ext not in _ALLOWED_EXTENSIONS:
            return JsonResponse({"error": "unsupported-file-type"}, status=400)
        if content_type and content_type not in _ALLOWED_CONTENT_TYPES:
            if content_type != "application/octet-stream":
                return JsonResponse({"error": "unsupported-file-type"}, status=400)
        size = getattr(uploaded, "size", 0) or 0
        if size > MAX_PLD_DOCUMENT_BYTES:
            return JsonResponse({"error": "file-too-large"}, status=400)

        existing = PLDExpedientDocument.objects.filter(
            expedient=exp, slot_key=slot_key
        ).first()
        if existing:
            if existing.file:
                existing.file.delete(save=False)
            doc = existing
        else:
            doc = PLDExpedientDocument(expedient=exp, slot_key=slot_key)
        doc.document_kind = slot["document_kind"]
        doc.original_filename = filename[:255]
        doc.content_type = content_type
        doc.file_size = size
        doc.uploaded_by = request.user
        doc.file.save(filename, uploaded, save=False)
        doc.save()
        return JsonResponse(_reload_my_expedient_row(entity.pk), status=200)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class MyPLDExpedientDocumentDetailView(View):
    def delete(self, request, entity_id, document_id, *args, **kwargs):
        entity, err = _invitee_counterparty_or_404(request, entity_id)
        if err:
            return err
        exp = entity.expedients.order_by("created_at").first()
        if not exp:
            return JsonResponse({"error": "Expedient not found"}, status=404)
        try:
            doc = PLDExpedientDocument.objects.get(pk=document_id, expedient=exp)
        except (PLDExpedientDocument.DoesNotExist, ValidationError, ValueError):
            return JsonResponse({"error": "Document not found"}, status=404)
        if doc.file:
            doc.file.delete(save=False)
        doc.delete()
        return JsonResponse(_reload_my_expedient_row(entity.pk), status=200)
