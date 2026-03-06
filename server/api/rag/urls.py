from django.urls import path
from .views import (
    DocumentView,
    query_collection,
    ChunkDetailView,
    QueryDocument,
    ChunkSetView,
    QueryCompletions,
)

app_name = "rag"

urlpatterns = [
    # path("test_chunks/", test_chunks, name="test_chunks"),
    path("documents/", DocumentView.as_view(), name="documents"),
    path(
        "documents/<int:document_id>/", DocumentView.as_view(), name="documents_detail"
    ),
    path(
        "documents/<int:document_id>/query/",
        QueryDocument.as_view(),
        name="documents_query",
    ),
    path("completions/query/", QueryCompletions.as_view(), name="completions_query"),
    path(
        "documents/<int:document_id>/chunks/", ChunkSetView.as_view(), name="chunk_set"
    ),
    path("query/", query_collection, name="query_collection"),
    path("chunks/<int:chunk_id>/", ChunkDetailView.as_view(), name="chunk_detail"),
]
