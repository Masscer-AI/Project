from django.contrib import admin

from api.compliance.models import ComplianceFolio, FolioDocument, FolioEvent


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
