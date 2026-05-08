from django.contrib import admin

from api.document_templates.models import DocumentTemplate, AgentDocumentTemplateAssignment


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")


@admin.register(AgentDocumentTemplateAssignment)
class AgentDocumentTemplateAssignmentAdmin(admin.ModelAdmin):
    list_display = ("agent", "template", "is_enabled", "created_at")
    list_filter = ("is_enabled",)
