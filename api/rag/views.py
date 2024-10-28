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
        serializer = BigDocumentSerializer(documents, many=True)
        return JsonResponse(serializer.data, safe=False)

    def post(self, request):
        data = request.POST.copy()
        data.pop("agent_slug", None)

        file = request.FILES.get("file")
        agents = request.POST.get("agents", None).split(",")
        # conversation_id = request.POST.get("conversation_id", None)

        if not file and (not agents):
            return JsonResponse(
                {
                    "message": "Bad request",
                    "error": "File and agents are required",
                },
                status=400,
            )

        file_content, file_name = read_file_content(file)
        file_content = file_content.strip()

        errors = []

        for agent_slug in agents:
            agent = Agent.objects.get(slug=agent_slug)

            if agent is None:
                errors.append(
                    {
                        "message": "Bad request",
                        "error": f"Agent with agent_slug {agent_slug} not found!",
                    }
                )
                continue

            collection, created = Collection.objects.get_or_create(
                agent=agent, defaults={"user": request.user}
            )

            document_exists = Document.objects.filter(
                text=file_content, collection=collection
            ).exists()

            if document_exists:
                continue

            data["collection"] = collection.id
            data["text"] = file_content

            serializer = DocumentSerializer(data=data)

            if serializer.is_valid():
                serializer.save()
                continue

        if len(errors) == 0:
            return JsonResponse(
                {"message": "Document created successfully"}, status=201
            )
        return JsonResponse(errors, status=400, safe=False)

    def delete(self, request, document_id):
        try:
            document = Document.objects.get(id=document_id)
            document.delete()
            return JsonResponse(
                {"message": "Document deleted successfully"}, status=204
            )
        except Document.DoesNotExist:
            return JsonResponse({"error": "Document not found"}, status=404)


@csrf_exempt
@token_required
def query_collection(request):
    data = json.loads(request.body)
    agent_slug = data.get("agent_slug", None)
    conversation_id = data.get("conversation_id", None)
    query_text = data.get("query", None)

    agent = Agent.objects.get(slug=agent_slug)

    collection = Collection.objects.get(agent=agent, user=request.user)

    if collection:
        messages = Message.objects.filter(conversation=conversation_id).order_by("-id")[
            :4
        ]
        _context = f"""
        These are the last four messages in the conversation:
        ---
        {" ".join([f'{m.type}: {m.text}\n' for m in messages])}
        ---

        This is the last user message text: {query_text}
        """
        queries = querify_context(context=_context, collection=collection)
        printer.success(
            "There is a collection for the requested agent, getting results from Chroma"
        )

        results = chroma_client.get_results(
            collection_name=collection.slug,
            query_texts=queries.queries,
            n_results=3,
        )

        data = {"results": results}
        return JsonResponse(data, safe=False)

    return JsonResponse({"error": "No collection found"}, status=404)


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
