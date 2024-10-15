from rest_framework import serializers
from .models import Collection, Document, Chunk

class ChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chunk
        fields = ['id', 'document', 'content', 'brief', 'tags','created_at']

class DocumentSerializer(serializers.ModelSerializer):
    chunk_set = ChunkSerializer(many=True, read_only=True)
    chunk_count = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ['id', 'collection', 'text', 'name', 'created_at', 'chunk_set', 'chunk_count']

    def get_chunk_count(self, obj):
        return obj.chunk_set.count()
    
class CollectionSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Collection
        fields = ['id', 'name', 'slug', 'chunk_size', 'chunk_overlap', 'user', 'created_at', 'agent', 'documents']
