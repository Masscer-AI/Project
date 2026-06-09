from django.contrib import admin

from api.assignments.models import UserAssignment


@admin.register(UserAssignment)
class UserAssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "key", "status", "organization", "created_at")
    list_filter = ("status", "key")
    search_fields = ("title", "user__email", "key")
    readonly_fields = ("id", "created_at", "updated_at")
