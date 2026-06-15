from django.contrib import admin

from api.data_governance.models import DataExportJob, DataPurgeLog, OrganizationDataPolicy


@admin.register(OrganizationDataPolicy)
class OrganizationDataPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "organization",
        "deleted_conversation_retention_days",
        "attachment_retention_days",
        "updated_at",
    )
    search_fields = ("organization__name",)


@admin.register(DataExportJob)
class DataExportJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "status",
        "requested_by",
        "file_size_bytes",
        "created_at",
        "expires_at",
    )
    list_filter = ("status",)
    search_fields = ("organization__name", "id")


@admin.register(DataPurgeLog)
class DataPurgeLogAdmin(admin.ModelAdmin):
    list_display = ("organization", "category", "count", "run_at")
    list_filter = ("category",)
