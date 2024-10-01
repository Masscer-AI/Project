from django.views import View
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Agent
from .serializers import AgentSerializer
from api.authenticate.decorators.token_required import token_required
from rest_framework.parsers import JSONParser


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class AgentView(View):
    def get(self, request, *args, **kwargs):
        request.user
        agents = Agent.objects.filter(user=request.user)
        print("RETURNING AGENTS FOR USER", agents)
        serializer = AgentSerializer(agents, many=True)
        return JsonResponse(serializer.data, safe=False)

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
