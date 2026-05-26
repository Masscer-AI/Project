from rest_framework import serializers
from .models import Collection, Document, Chunk
from api.ai_layers.serializers import AgentSerializer


class ChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chunk
        fields = ["id", "document", "content", "brief", "tags", "created_at"]


class MiniCollectionSerializer(serializers.ModelSerializer):
    agent = AgentSerializer()

    class Meta:
        model = Collection
        fields = ["id", "name", "chunk_size", "chunk_overlap", "agent"]


class DocumentSerializer(serializers.ModelSerializer):
    # chunk_set = ChunkSerializer(many=True, read_only=True)
    chunk_count = serializers.SerializerMethodField()
    has_file = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "collection",
            "text",
            "name",
            "content_type",
            "created_at",
            "chunk_set",
            "chunk_count",
            "brief",
            "total_tokens",
            "has_file",
            "file_url",
        ]

    def get_chunk_count(self, obj):
        return obj.chunk_set.count()

    def get_has_file(self, obj):
        return bool(getattr(obj, "file", None))

    def get_file_url(self, obj):
        file_field = getattr(obj, "file", None)
        if not file_field:
            return None
        request = self.context.get("request")
        try:
            url = file_field.url
        except Exception:
            return None
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class BigDocumentSerializer(serializers.ModelSerializer):
    chunk_set = ChunkSerializer(many=True, read_only=True)
    chunk_count = serializers.SerializerMethodField()
    collection = MiniCollectionSerializer(read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "collection",
            "text",
            "name",
            "created_at",
            "chunk_set",
            "chunk_count",
            "brief",
            "total_tokens",
        ]

    def get_chunk_count(self, obj):
        return obj.chunk_set.count()


class CollectionSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Collection
        fields = [
            "id",
            "name",
            "slug",
            "chunk_size",
            "chunk_overlap",
            "user",
            "created_at",
            "agent",
            "documents",
        ]
