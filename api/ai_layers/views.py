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
from api.utils.ollama_functions import list_ollama_models

OPENAI_MODELS = [
    {
        "name": "gpt-4o",
        "slug": "gpt-4o",
        "provider": "openai",
        "selected": False,
        "type": "model",
    },
    {
        "name": "gpt-4o-mini",
        "slug": "gpt-4o-mini",
        "provider": "openai",
        "selected": False,
        "type": "model",
    },
]


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class AgentView(View):
    def get(self, request, *args, **kwargs):
        request.user
        agents = Agent.objects.filter(user=request.user)
        models = LanguageModel.objects.all()
        serializer_data = AgentSerializer(agents, many=True).data
        models_data = LanguageModelSerializer(models, many=True).data

        models_and_agents = [
            {
                "name": a["name"],
                "slug": a["slug"],
                "model_slug": a["model_slug"],
                "provider": a["model_provider"],
                "selected": False,
                "type": "agent",
            }
            for a in serializer_data
        ]
        models_and_agents[0]["selected"] = True
        models_and_agents.extend(
            [
                {
                    "name": m["name"],
                    "slug": m["slug"],
                    "provider": m["provider"],
                    "selected": False,
                    "type": "model",
                }
                for m in models_data
            ]
        )
        models_and_agents.extend(OPENAI_MODELS)
        return JsonResponse(models_and_agents, safe=False)

    def post(self, request, *args, **kwargs):
        data = JSONParser().parse(request)
        serializer = AgentSerializer(data=data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return JsonResponse(serializer.data, status=201)
        return JsonResponse(serializer.errors, status=400)

    def delete(self, request, *args, **kwargs):
        agent_id = kwargs.get("id")
        agent = get_object_or_404(Agent, id=agent_id)
        agent.delete()
        return JsonResponse({"message": "Agent deleted successfully"})


@csrf_exempt
@token_required
def get_formatted_system_prompt(request):
    body = json.loads(request.body)
    agent = Agent.objects.get(slug=body.get("agent_slug", "useful-assistant"))
    system = agent.format_prompt(context=body.get("context"))
    return JsonResponse({"system_prompt": system})
