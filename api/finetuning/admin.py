from django.contrib import admin
from .models import TrainingGenerator, Completion
from .actions import start_generator

# Register your models here.


@admin.register(TrainingGenerator)
class TrainingGeneratorAdmin(admin.ModelAdmin):
    list_display = ["id", "agent", "created_at"]

    list_filter = ["agent"]
    search_fields = ["agent__name"]

    actions = ["_start_generator"]

    def _start_generator(self, request, queryset):
        for generator in queryset:
            start_generator(generator.id)


@admin.register(Completion)
class CompletionAdmin(admin.ModelAdmin):
    list_display = ["id", "prompt", "answer", "created_at"]
    # list_filter = ["training_generator__agent"]
    # search_fields = ["training_generator__agent__name"]
