from django.urls import path
from .views import Transcriptions

app_name = "tools"

urlpatterns = [
    path('transcriptions/', Transcriptions.as_view(), name='transcriptions'),
]