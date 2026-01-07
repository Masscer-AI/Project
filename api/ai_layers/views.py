from django.views import View
import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Q
from .models import Agent, LanguageModel
from .serializers import AgentSerializer, LanguageModelSerializer
from api.authenticate.decorators.token_required import token_required
from api.authenticate.models import Organization
from rest_framework.parsers import JSONParser
from api.utils.color_printer import printer
from api.authenticate.models import UserProfile
from faker import Faker
import random
from django.core.cache import cache

CACHE_TIMEOUT = 60 * 60 * 24

fake = Faker()


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class AgentView(View):
    def get(self, request, *args, **kwargs):
        # Get user's organization first
        user_org = None
        if hasattr(request.user, 'profile') and request.user.profile.organization:
            user_org = request.user.profile.organization
        
        # Generar una clave única para el caché basado en el usuario Y su organización
        # Esto asegura que si la organización cambia o se agregan agentes, se invalida el caché
        org_id = user_org.id if user_org else "no_org"
        cache_key = f"agent_data_{request.user.id}_{org_id}"
        cached_data = cache.get(cache_key)

        # Si los datos están en el caché, devolverlos directamente
        if cached_data:
            return JsonResponse(cached_data, safe=False)

        # Obtener agentes del usuario Y de su organización
        # TODOS los miembros de la organización pueden VER los agentes de la organización
        # La feature flag NO afecta la visibilidad, solo los permisos de edición/eliminación
        if user_org:
            agents = Agent.objects.filter(Q(user=request.user) | Q(organization=user_org))
        else:
            agents = Agent.objects.filter(user=request.user)
        
        models = LanguageModel.objects.all()
        agents_data = AgentSerializer(agents, many=True).data
        models_data = LanguageModelSerializer(models, many=True).data

        data = {"models": models_data, "agents": agents_data}

        cache.set(cache_key, data, timeout=CACHE_TIMEOUT)

        return JsonResponse(data, safe=False)

    def put(self, request, *args, **kwargs):
        from api.authenticate.services import FeatureFlagService
        
        default_llm = {
            "provider": "openai",
            "slug": "gpt-4o-mini",
        }

        agent_slug = kwargs.get("slug")
        
        # Get user's organization
        user_org = None
        if hasattr(request.user, 'profile') and request.user.profile.organization:
            user_org = request.user.profile.organization
        
        # Check permissions: user can edit their own agents OR organization agents if they have the flag
        has_admin_flag = FeatureFlagService.is_feature_enabled(
            "organization-agents-admin",
            organization=user_org,
            user=request.user
        )
        
        # Build query for agent
        if has_admin_flag and user_org:
            agent = get_object_or_404(
                Agent.objects.filter(
                    Q(user=request.user) | Q(organization=user_org),
                    slug=agent_slug
                )
            )
        else:
            agent = get_object_or_404(Agent, slug=agent_slug, user=request.user)
        
        # Check if user can actually edit this agent
        can_edit = (agent.user == request.user) or (has_admin_flag and agent.organization == user_org)
        if not can_edit:
            return JsonResponse({"error": "You don't have permission to edit this agent"}, status=403)
        
        data = JSONParser().parse(request)

        llm_slug = data.get("llm", default_llm).get("slug")
        llm_provider = data.get("llm", default_llm).get("provider")
        llm = LanguageModel.objects.get(slug=llm_slug, provider__name=llm_provider)

        agent.llm = llm

        serializer = AgentSerializer(agent, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()

            # Invalidar el caché después de actualizar
            # Invalidate cache for user
            user_org = None
            if hasattr(request.user, 'profile') and request.user.profile.organization:
                user_org = request.user.profile.organization
            
            org_id = user_org.id if user_org else "no_org"
            cache_key = f"agent_data_{request.user.id}_{org_id}"
            cache.delete(cache_key)
            
            # If agent belongs to organization, invalidate cache for all org members
            if agent.organization:
                from django.contrib.auth.models import User
                org_members = User.objects.filter(profile__organization=agent.organization)
                for member in org_members:
                    member_org_id = agent.organization.id
                    member_cache_key = f"agent_data_{member.id}_{member_org_id}"
                    cache.delete(member_cache_key)

            return JsonResponse(serializer.data, status=200)
        return JsonResponse(serializer.errors, status=400)

    def post(self, request, *args, **kwargs):
        data = JSONParser().parse(request)

        serializer = AgentSerializer(data=data)
        if serializer.is_valid():
            serializer.save(user=request.user)

            # Invalidar el caché después de crear un nuevo agente
            user_org = None
            if hasattr(request.user, 'profile') and request.user.profile.organization:
                user_org = request.user.profile.organization
            
            org_id = user_org.id if user_org else "no_org"
            cache_key = f"agent_data_{request.user.id}_{org_id}"
            cache.delete(cache_key)
            
            # If agent belongs to organization, invalidate cache for all org members
            if serializer.instance and serializer.instance.organization:
                from django.contrib.auth.models import User
                org_members = User.objects.filter(profile__organization=serializer.instance.organization)
                for member in org_members:
                    member_org_id = serializer.instance.organization.id
                    member_cache_key = f"agent_data_{member.id}_{member_org_id}"
                    cache.delete(member_cache_key)

            return JsonResponse(serializer.data, status=201)
        return JsonResponse(serializer.errors, status=400)

    def delete(self, request, *args, **kwargs):
        from api.authenticate.services import FeatureFlagService
        
        agent_slug = kwargs.get("slug")
        
        # Get user's organization
        user_org = None
        if hasattr(request.user, 'profile') and request.user.profile.organization:
            user_org = request.user.profile.organization
        
        # Check permissions
        has_admin_flag = FeatureFlagService.is_feature_enabled(
            "organization-agents-admin",
            organization=user_org,
            user=request.user
        )
        
        # Build query for agent
        if has_admin_flag and user_org:
            agent = get_object_or_404(
                Agent.objects.filter(
                    Q(user=request.user) | Q(organization=user_org),
                    slug=agent_slug
                )
            )
        else:
            agent = get_object_or_404(Agent, slug=agent_slug, user=request.user)
        
        # Check if user can actually delete this agent
        can_delete = (agent.user == request.user) or (has_admin_flag and agent.organization == user_org)
        if not can_delete:
            return JsonResponse({"error": "You don't have permission to delete this agent"}, status=403)
        
        # Capture organization before deleting
        agent_org = agent.organization
        agent.delete()

        # Invalidar el caché después de eliminar un agente
        user_org = None
        if hasattr(request.user, 'profile') and request.user.profile.organization:
            user_org = request.user.profile.organization
        
        org_id = user_org.id if user_org else "no_org"
        cache_key = f"agent_data_{request.user.id}_{org_id}"
        cache.delete(cache_key)
        
        # If agent belonged to organization, invalidate cache for all org members
        if agent_org:
            from django.contrib.auth.models import User
            org_members = User.objects.filter(profile__organization=agent_org)
            for member in org_members:
                member_org_id = agent_org.id
                member_cache_key = f"agent_data_{member.id}_{member_org_id}"
                cache.delete(member_cache_key)

        return JsonResponse({"message": "Agent deleted successfully"})


@csrf_exempt
@token_required
def get_formatted_system_prompt(request):
    body = json.loads(request.body)
    profile = UserProfile.objects.get(user=request.user)

    agent = Agent.objects.get(slug=body.get("agent_slug", "useful-assistant"))
    system = agent.format_prompt(context=body.get("context"))
    if profile:
        system += profile.get_as_text()
    agent_data = AgentSerializer(agent).data
    agent_data["formatted"] = system
    return JsonResponse(agent_data)


@csrf_exempt
@token_required
def create_random_agent(request):
    printer.yellow("Creating random agent")
    if request.method != "POST":
        return JsonResponse({"error": "Only POST requests are allowed."}, status=405)

    name = fake.name()
    model_slug = random.choice(["gpt-4o-mini", "gpt-4o", "chatgpt-4o-latest"])
    salute = fake.sentence()
    llm = LanguageModel.objects.get(slug=model_slug)
    act_as = "You are a helpful assistant."
    user = request.user if request.user.is_authenticated else None
    printer.blue("User", user)
    # Create the agent instance
    agent = Agent(
        name=name,
        model_slug=model_slug,
        salute=salute,
        act_as=act_as,
        user=user,
        llm=llm,
    )

    agent.save()

    cache_key = f"agent_data_{request.user.id}"
    cache.delete(cache_key)

    return JsonResponse(agent.serialize(), status=201)
