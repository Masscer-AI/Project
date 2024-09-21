from django.contrib import admin
from .models import Token

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('key', 'user', 'token_type', 'expires_at', 'created_at', 'updated_at')
    search_fields = ('key', 'user__username', 'token_type')
    list_filter = ('token_type', 'expires_at', 'created_at', 'updated_at')
