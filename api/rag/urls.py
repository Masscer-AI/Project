from django.urls import path
from .views import test_chunks

app_name = "rag"

urlpatterns = [
    path("test_chunks/", test_chunks, name="test_chunks"),
]
