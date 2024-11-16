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
        ]

    def get_chunk_count(self, obj):
        return obj.chunk_set.count()


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
