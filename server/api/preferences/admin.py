from django.contrib import admin
from .models import UserPreferences, UserVoices

admin.site.register(UserPreferences)

admin.site.register(UserVoices)
