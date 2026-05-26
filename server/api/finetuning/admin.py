from django.contrib import admin

from .actions import start_generator
from .models import Completion, CompletionAssignment, TrainingGenerator


class CompletionAssignmentInline(admin.TabularInline):
    model = CompletionAssignment
    extra = 0


@admin.register(TrainingGenerator)
class TrainingGeneratorAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "status", "created_at"]
    filter_horizontal = ["agents"]
    search_fields = ["name"]

    actions = ["_start_generator"]

    def _start_generator(self, request, queryset):
        for generator in queryset:
            start_generator(generator.id)


@admin.register(Completion)
class CompletionAdmin(admin.ModelAdmin):
    list_display = ["id", "prompt", "approved", "created_at"]
    list_filter = ["approved"]
    inlines = [CompletionAssignmentInline]
