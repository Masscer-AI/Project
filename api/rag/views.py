# import os
import json
from django.http import JsonResponse
from .managers import chroma_client
from django.views import View
from rest_framework.parsers import JSONParser

import logging
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Document, Collection, Chunk
from api.authenticate.decorators.token_required import token_required
from .serializers import DocumentSerializer, ChunkSerializer, BigDocumentSerializer
from api.ai_layers.models import Agent
from rest_framework.parsers import MultiPartParser
from .actions import read_file_content
from api.messaging.models import Message
from api.utils.color_printer import printer
from .actions import querify_context

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class DocumentView(View):
    parser_classes = (MultiPartParser,)

    def get(self, request):
        user = request.user
        documents = Document.objects.filter(collection__user=user)
        serializer = DocumentSerializer(documents, many=True)
        return JsonResponse(serializer.data, safe=False)

    def post(self, request):
        data = request.POST.copy()
        data.pop("agent_slug", None)

        file = request.FILES.get("file")

        collection, created = Collection.objects.get_or_create(
            user=request.user, agent=None, conversation=None
        )
        if not collection:
            return JsonResponse(
                {
                    "message": "Bad request",
                    "error": "Collection not found",
                },
                status=400,
            )

        if not file:
            return JsonResponse(
                {
                    "message": "Bad request",
                    "error": "File are required",
                },
                status=400,
            )

        file_content, file_name = read_file_content(file)
        file_content = file_content.strip()

        document_exists = Document.objects.filter(
            text=file_content, collection=collection
        ).exists()

        if document_exists:
            document = Document.objects.get(text=file_content, collection=collection)

            serializer = DocumentSerializer(document)
            return JsonResponse(serializer.data, status=200)

        data["collection"] = collection.id
        if not data.get("name") and file_name:
            data["name"] = file_name
        data["text"] = file_content.replace("\0", "")
        serializer = DocumentSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data, status=201)

        return JsonResponse(serializer.errors, status=400)

    def put(self, request, document_id):
        data = json.loads(request.body)
        action = data.get("action", None)

        document = Document.objects.get(id=document_id)
        if action == "add":
            document.add_to_rag()
        elif action == "remove":
            document.remove_from_rag()
        elif action == "generate_brief":
            document.generate_brief()

        return JsonResponse(DocumentSerializer(document).data, status=200)

    def delete(self, request, document_id):
        try:
            document = Document.objects.get(id=document_id)
            document.remove_from_rag()
            return JsonResponse(
                {"message": "Document deleted successfully"}, status=200
            )
        except Document.DoesNotExist:
            return JsonResponse({"error": "Document not found"}, status=404)


@csrf_exempt
@token_required
def query_collection(request):
    data = json.loads(request.body)
    # agent_slug = data.get("agent_slug", None)
    conversation_id = data.get("conversation_id", None)
    document_id = data.get("document_id", None)
    query_text = data.get("query", None)
    collection_id = data.get("collection_id", None)

    collection = Collection.objects.get(user=request.user, pk=collection_id)

    if collection:
        messages = Message.objects.filter(conversation=conversation_id).order_by("-id")[
            :4
        ]

        if document_id:
            document = Document.objects.get(id=document_id)

        _context = f"""
        These are the last four messages in the conversation:
        ---
        {" ".join([f'{m.type}: {m.text}' for m in messages])}
        ---

        This is the last user message text: {query_text}
        """

        if document:
            _context += f"""
            This is a brief from the document the user wants to query: 
            ---
            {document.brief}
            ---
            """

        queries = querify_context(context=_context)
        printer.success(
            "There is a collection for the user, getting results from Chroma"
        )

        printer.blue(f"Queries: {queries.queries}")
        printer.yellow(f"Document: {document}")
        results = chroma_client.get_results(
            collection_name=collection.slug, query_texts=queries.queries, n_results=4
        )

        data = {"results": results}
        return JsonResponse(data, safe=False)

    return JsonResponse({"error": "No collection found"}, status=404)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ChunkSetView(View):
    def get(self, request, document_id):
        document = Document.objects.get(id=document_id)
        data = BigDocumentSerializer(document).data
        return JsonResponse(data, status=201)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ChunkDetailView(View):
    parser_classes = (JSONParser,)

    def get(self, request, chunk_id):
        try:
            chunk = Chunk.objects.get(id=chunk_id)
            serializer = ChunkSerializer(chunk)
            return JsonResponse(serializer.data, safe=False, status=200)
        except Chunk.DoesNotExist:
            return JsonResponse({"error": "Chunk not found"}, status=404)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class QueryDocument(View):
    def post(self, request, document_id):
        data = json.loads(request.body)
        query_text = data.get("query", None)
        conversation_id = data.get("conversation_id", None)

        document = Document.objects.get(id=document_id)
        collection = document.collection

        messages = Message.objects.filter(conversation=conversation_id).order_by("-id")[
            :4
        ]

        _context = f"""
        These are the last four messages in the conversation:
        ---
        {" ".join([f'{m.type}: {m.text}' for m in messages])}
        ---

        This is a summary of the document the user wants to query:
        ---
        {document.brief}
        ---

        This is the last user message text: {query_text}
        """

        queries = querify_context(context=_context)
        printer.success(
            "There is a collection for the user, getting results from Chroma"
        )

        printer.blue(f"Queries: {queries.queries}")
        printer.yellow(f"Document: {document}")

        results = chroma_client.get_results(
            collection_name=collection.slug,
            query_texts=queries.queries,
            n_results=4,
            where={"extra": document.get_representation()},
        )

        data = {"results": results}
        return JsonResponse(data, safe=False)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class QueryCompletions(View):
    def post(self, request):
        data = json.loads(request.body)
        query_text = data.get("query", None)
        agent_slug = data.get("agent_slug", None)

        agent = Agent.objects.get(slug=agent_slug)

        if not agent:
            # Return a 404
            return JsonResponse({"error": "Agent not found"}, status=404)
        collection, created = Collection.objects.get_or_create(
            user=request.user, agent=agent
        )
        if created:
            printer.success("No collection found for the agent, creating a new one")
            return JsonResponse([], status=200, safe=False)

        queries = querify_context(context=query_text)
        printer.success(
            "There is a collection for the agent, getting results from Chroma"
        )

        results = chroma_client.get_results(
            collection_name=collection.slug,
            query_texts=queries.queries,
            n_results=4,
        )

        data = {"results": results}
        return JsonResponse(data, safe=False)
