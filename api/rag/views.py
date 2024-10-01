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

        if not file or not agent_slug:
            return JsonResponse(
                {
                    "message": "Bad request",
                    "error": "File and agent_slug are required!",
                },
                status=400,
            )

        file_content, file_name = read_file_content(file)
        file_content = file_content.strip()
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
            return JsonResponse(
                {
                    "message": "Conflict",
                    "error": "File with the same content already exists!",
                },
                status=409,
            )

        data["collection"] = collection.id
        data["text"] = file_content

        logger.debug("Received post request in Document view")
        logger.debug(data)
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

    print(agent_slug, "AGENT SLUG TO RETRIEVE RESULTS")
    query_text = data.get("query", None)
    print(query_text, "QUERY TEXT RETRIEVE RESULTS")

    agent = Agent.objects.get(slug=agent_slug)

    collection, created = Collection.objects.get_or_create(
        agent=agent, defaults={"user": request.user}
    )

    results = chroma_client.get_results(
        collection_name=collection.slug, query_text=query_text, n_results=4
    )

    data = {"results": results}
    return JsonResponse(data, safe=False)
