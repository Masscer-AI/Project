from django.views import View
import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Agent, LanguageModel
from .serializers import AgentSerializer, LanguageModelSerializer
from api.authenticate.decorators.token_required import token_required
from rest_framework.parsers import JSONParser
from api.utils.color_printer import printer


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class AgentView(View):
    def get(self, request, *args, **kwargs):
        request.user
        agents = Agent.objects.filter(user=request.user)
        models = LanguageModel.objects.all()
        agents_data = AgentSerializer(agents, many=True).data
        models_data = LanguageModelSerializer(models, many=True).data

        data = {"models": models_data, "agents": agents_data}
        return JsonResponse(data, safe=False)

    def put(self, request, *args, **kwargs):

        agent_slug = kwargs.get("slug")
        agent = get_object_or_404(Agent, slug=agent_slug, user=request.user)
        data = JSONParser().parse(request)
        printer.blue("Request saving agent",data)
        llm = LanguageModel.objects.get(slug=data.get("model_slug", "gpt-4o-mini"))

        agent.llm = llm

        serializer = AgentSerializer(agent, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data, status=200)
        return JsonResponse(serializer.errors, status=400)

    def post(self, request, *args, **kwargs):
        data = JSONParser().parse(request)

        serializer = AgentSerializer(data=data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return JsonResponse(serializer.data, status=201)
        return JsonResponse(serializer.errors, status=400)

    def delete(self, request, *args, **kwargs):
        agent_slug = kwargs.get("slug")
        agent = get_object_or_404(Agent, slug=agent_slug, user=request.user)
        agent.delete()
        return JsonResponse({"message": "Agent deleted successfully"})


@csrf_exempt
@token_required
def get_formatted_system_prompt(request):
    body = json.loads(request.body)
    agent = Agent.objects.get(slug=body.get("agent_slug", "useful-assistant"))
    system = agent.format_prompt(context=body.get("context"))
    agent_data = AgentSerializer(agent).data
    agent_data["formatted"] = system
    return JsonResponse(agent_data)
