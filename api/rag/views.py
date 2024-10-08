# import os
import json
from django.http import JsonResponse
from .managers import chroma_client
from django.views import View

import logging
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Document, Collection
from api.authenticate.decorators.token_required import token_required
from .serializers import DocumentSerializer
from api.ai_layers.models import Agent
from rest_framework.parsers import MultiPartParser
from .actions import read_file_content
from api.messaging.models import Conversation

logger = logging.getLogger(__name__)


def test_chunks(request):
    collection_name = "hotel-alpha-india"
    query_text = request.GET.get("q", "Where did you study?")
    collection = chroma_client.client.get_collection(collection_name)
    count = collection.count()
    print(count, "NOMBER OF VERGAS")
    results = chroma_client.get_results(
        collection_name=collection_name, query_text=query_text, n_results=1
    )

    data = {"results": results}
    return JsonResponse(data)


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
        agent_slug = request.POST.get("agent_slug", None)
        conversation_id = request.POST.get("conversation_id", None)
        print("conversation_id", conversation_id)
        if not file and (not agent_slug or not conversation_id):
            return JsonResponse(
                {
                    "message": "Bad request",
                    "error": "File and agent_slug or conversation_id are required",
                },
                status=400,
            )
        print(type(file), "TIPE OF FILE")

        file_content, file_name = read_file_content(file)
        file_content = file_content.strip()

        if conversation_id:
            c = Conversation.objects.get(pk=conversation_id)
            if c is None:
                return JsonResponse(
                    {
                        "message": "Bad request",
                        "error": f"Conversation with conversation_id {conversation_id} not found!",
                    },
                    status=404,
                )

            collection, created = Collection.objects.get_or_create(
                conversation=c, defaults={"user": request.user}
            )
            document_exists = Document.objects.filter(
                text=file_content, collection=collection
            ).exists()
            if document_exists:
                existing_document = Document.objects.get(
                    text=file_content, collection=collection
                )
                existing_serializer = DocumentSerializer(existing_document)
                return JsonResponse(existing_serializer.data, status=200)

            data["collection"] = collection.id
            data["text"] = file_content
            serializer = DocumentSerializer(data=data)

            if serializer.is_valid():
                serializer.save()
                return JsonResponse(serializer.data, status=201)
            return JsonResponse(serializer.errors, status=400)

        agent = Agent.objects.get(slug=agent_slug)

        if agent is None:
            return JsonResponse(
                {
                    "message": "Bad request",
                    "error": f"Agent with agent_slug {agent_slug} not found!",
                },
                status=404,
            )

        collection, created = Collection.objects.get_or_create(
            agent=agent, defaults={"user": request.user}
        )

        document_exists = Document.objects.filter(
            text=file_content, collection=collection
        ).exists()

        if document_exists:
            existing_document = Document.objects.get(
                text=file_content, collection=collection
            )
            existing_serializer = DocumentSerializer(existing_document)
            return JsonResponse(existing_serializer.data, status=200)

        data["collection"] = collection.id
        data["text"] = file_content

        # logger.debug("Received post request in Document view")
        # logger.debug(data)
        serializer = DocumentSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data, status=201)
        return JsonResponse(serializer.errors, status=400)

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

    if conversation_id:
        c = Conversation.objects.get(pk=conversation_id)
        collection, created = Collection.objects.get_or_create(
            conversation=c, defaults={"user": request.user}
        )
        results = chroma_client.get_results(
            collection_name=collection.slug, query_text=query_text, n_results=6
        )
        data = {"results": results}
        return JsonResponse(data, safe=False)

    agent = Agent.objects.get(slug=agent_slug)

    collection, created = Collection.objects.get_or_create(
        agent=agent, defaults={"user": request.user}
    )

    results = chroma_client.get_results(
        collection_name=collection.slug, query_text=query_text, n_results=6
    )

    data = {"results": results}
    return JsonResponse(data, safe=False)
