from django.contrib import admin
from .models import UserPreferences, UserVoices


# Register your models here.
admin.site.register(UserPreferences)

admin.site.register(UserVoices)
