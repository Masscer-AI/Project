from django.contrib import admin

from api.compliance.models import (
    ComplianceFolio,
    FolioDocument,
    FolioEvent,
    PLDClarificationRequest,
    PLDEntity,
    PLDExpedient,
    PLDExpedientDocument,
    PLDInvite,
    WatchlistRecord,
    WatchlistSnapshot,
)


class FolioDocumentInline(admin.TabularInline):
    model = FolioDocument
    extra = 0
    fields = ("id", "document_kind", "status", "attachment", "notes", "created_at")
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("attachment",)
    show_change_link = True


class FolioEventInline(admin.TabularInline):
    model = FolioEvent
    extra = 0
    fields = ("event_type", "folio_document", "actor", "payload", "created_at")
    readonly_fields = ("event_type", "folio_document", "actor", "payload", "created_at")
    can_delete = False
    ordering = ("created_at",)


@admin.register(ComplianceFolio)
class ComplianceFolioAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "subject_user", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("subject_user__email", "subject_user__username", "notes")
    raw_id_fields = ("organization", "subject_user")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [FolioDocumentInline, FolioEventInline]


@admin.register(FolioDocument)
class FolioDocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "folio", "document_kind", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("folio", "attachment")
    readonly_fields = ("id", "created_at", "updated_at")


class PLDExpedientInline(admin.TabularInline):
    model = PLDExpedient
    extra = 0
    fields = (
        "id",
        "status",
        "vulnerable_activity",
        "started_at",
        "created_at",
    )
    readonly_fields = ("id", "created_at")
    show_change_link = True


@admin.register(PLDEntity)
class PLDEntityAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "person_type",
        "relationship",
        "email",
        "user",
        "updated_at",
    )
    list_filter = ("person_type", "relationship")
    search_fields = ("email", "user__email", "user__username")
    raw_id_fields = ("organization", "user")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [PLDExpedientInline]


@admin.register(PLDInvite)
class PLDInviteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "entity",
        "email",
        "status",
        "invite_expires_at",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("email",)
    raw_id_fields = ("organization", "entity", "invited_by", "accepted_user")
    readonly_fields = ("id", "token_hash", "created_at", "updated_at")


class PLDExpedientDocumentInline(admin.TabularInline):
    model = PLDExpedientDocument
    extra = 0
    fields = (
        "id",
        "slot_key",
        "document_kind",
        "original_filename",
        "file",
        "uploaded_by",
        "created_at",
    )
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("uploaded_by",)


class PLDClarificationRequestInline(admin.TabularInline):
    model = PLDClarificationRequest
    extra = 0
    fields = (
        "id",
        "stage",
        "status",
        "answer_type",
        "prompt",
        "text_answer",
        "created_at",
    )
    readonly_fields = ("id", "created_at")
    show_change_link = True


@admin.register(PLDExpedient)
class PLDExpedientAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "entity",
        "status",
        "vulnerable_activity",
        "started_at",
        "updated_at",
    )
    list_filter = ("status", "vulnerable_activity")
    raw_id_fields = ("organization", "entity")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [PLDExpedientDocumentInline, PLDClarificationRequestInline]


@admin.register(PLDExpedientDocument)
class PLDExpedientDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "expedient",
        "slot_key",
        "document_kind",
        "original_filename",
        "created_at",
    )
    list_filter = ("document_kind",)
    raw_id_fields = ("expedient", "uploaded_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(WatchlistSnapshot)
class WatchlistSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "list_slug",
        "date_generated",
        "file_sha256",
        "record_count",
        "is_current",
        "status",
        "ingested_at",
    )
    list_filter = ("list_slug", "status", "is_current")
    search_fields = ("file_sha256", "date_generated", "source_url")
    readonly_fields = (
        "id",
        "list_slug",
        "source_url",
        "file_sha256",
        "content_length",
        "date_generated",
        "status",
        "is_current",
        "record_count",
        "error",
        "ingested_at",
    )


@admin.register(WatchlistRecord)
class WatchlistRecordAdmin(admin.ModelAdmin):
    list_display = (
        "reference_number",
        "record_type",
        "primary_name",
        "listed_on",
        "snapshot",
    )
    list_filter = ("record_type", "snapshot__list_slug", "snapshot__is_current")
    search_fields = ("reference_number", "primary_name", "search_document", "data_id")
    raw_id_fields = ("snapshot",)
    readonly_fields = (
        "id",
        "snapshot",
        "record_type",
        "reference_number",
        "data_id",
        "primary_name",
        "listed_on",
        "names",
        "dates_of_birth",
        "document_numbers",
        "nationalities",
        "search_document",
        "raw",
    )
