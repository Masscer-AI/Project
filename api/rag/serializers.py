from rest_framework import serializers
from .models import Collection, Document, Chunk

class ChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chunk
        fields = ['id', 'document', 'content', 'brief', 'created_at']

class DocumentSerializer(serializers.ModelSerializer):
    chunks = ChunkSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = ['id', 'collection', 'text', 'name', 'created_at', 'chunks']

class CollectionSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Collection
        fields = ['id', 'name', 'slug', 'chunk_size', 'chunk_overlap', 'user', 'created_at', 'agent', 'documents']
