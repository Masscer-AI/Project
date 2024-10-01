from django.urls import path
from .views import test_chunks, DocumentView, query_collection

app_name = "rag"

urlpatterns = [
    path("test_chunks/", test_chunks, name="test_chunks"),
    path("documents/", DocumentView.as_view(), name="documents"),
    path("query/", query_collection, name="query_collection"),
]
