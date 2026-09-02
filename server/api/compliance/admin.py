from django.contrib import admin

from api.compliance.models import (
    ComplianceFolio,
    FolioDocument,
    FolioEvent,
    PLDEntity,
    PLDExpedient,
    PLDInvite,
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
