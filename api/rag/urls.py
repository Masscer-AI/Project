from django.urls import path
from .views import DocumentView, query_collection, ChunkDetailView

app_name = "rag"

urlpatterns = [
    # path("test_chunks/", test_chunks, name="test_chunks"),
    path("documents/", DocumentView.as_view(), name="documents"),
    path("documents/<int:document_id>/", DocumentView.as_view(), name="documents"),
    path("query/", query_collection, name="query_collection"),
    path("chunks/<int:chunk_id>/", ChunkDetailView.as_view(), name="chunk_detail"),
]
