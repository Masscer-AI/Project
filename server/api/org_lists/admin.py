from django.contrib import admin

from api.org_lists.models import OrganizationList, OrganizationListRecord
from api.org_lists.tasks import process_organization_list_import


class OrganizationListRecordInline(admin.TabularInline):
    model = OrganizationListRecord
    extra = 0
    fields = ("position", "data_preview", "id")
    readonly_fields = ("position", "data_preview", "id")
    can_delete = False
    show_change_link = True
    max_num = 20

    @admin.display(description="Data")
    def data_preview(self, obj: OrganizationListRecord) -> str:
        text = str(obj.data or {})
        return text[:200] + ("…" if len(text) > 200 else "")


@admin.register(OrganizationList)
class OrganizationListAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "import_status",
        "record_count",
        "updated_at",
    )
    list_filter = ("import_status",)
    search_fields = ("name", "organization__name")
    raw_id_fields = ("organization", "uploaded_by")
    readonly_fields = (
        "id",
        "config",
        "record_count",
        "import_error",
        "created_at",
        "updated_at",
    )
    inlines = [OrganizationListRecordInline]
    actions = ["rerun_import"]

    @admin.action(description="Re-run import from stored file")
    def rerun_import(self, request, queryset):
        for org_list in queryset:
            org_list.import_status = OrganizationList.ImportStatus.PENDING
            org_list.import_error = ""
            org_list.save(update_fields=["import_status", "import_error", "updated_at"])
            process_organization_list_import.delay(str(org_list.id))


@admin.register(OrganizationListRecord)
class OrganizationListRecordAdmin(admin.ModelAdmin):
    list_display = ("organization_list", "position")
    list_filter = ("organization_list",)
    search_fields = ("search_document",)
    raw_id_fields = ("organization_list",)
    readonly_fields = ("id",)
