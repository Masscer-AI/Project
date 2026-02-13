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
from api.authenticate.decorators.feature_flag_required import feature_flag_required
from api.authenticate.models import Organization
from api.providers.models import AIProvider
from rest_framework.parsers import JSONParser
from api.utils.color_printer import printer
from api.authenticate.models import UserProfile
from faker import Faker
import random
from django.core.cache import cache
from django.contrib.auth.models import User

CACHE_TIMEOUT = 60 * 60 * 24

fake = Faker()


def _invalidate_agent_cache_for_user_and_org(user, organization=None):
    org_id = organization.id if organization else "no_org"
    cache.delete(f"agent_data_{user.id}_{org_id}")

    if not organization:
        return

    org_members = User.objects.filter(
        Q(profile__organization=organization) | Q(id=organization.owner_id)
    ).distinct()
    for member in org_members:
        cache.delete(f"agent_data_{member.id}_{organization.id}")


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
        has_admin_flag, _ = FeatureFlagService.is_feature_enabled(
            "edit-organization-agent",
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

        # --- Handle ownership change (personal ↔ organization) ---
        ownership = data.pop("ownership", None)  # "personal" | "<organization_id>"
        if ownership is not None:
            can_set_ownership, _ = FeatureFlagService.is_feature_enabled(
                "set-agent-ownership", organization=user_org, user=request.user
            )
            is_org_owner = user_org and user_org.owner_id == request.user.id
            if not (can_set_ownership or is_org_owner):
                return JsonResponse(
                    {"error": "You don't have permission to change agent ownership"},
                    status=403,
                )

            old_org = agent.organization
            if ownership == "personal":
                agent.organization = None
                agent.user = request.user
            else:
                try:
                    target_org = Organization.objects.get(id=ownership)
                except Organization.DoesNotExist:
                    return JsonResponse({"error": "Organization not found"}, status=404)
                # Verify the user belongs to (or owns) the target org
                is_member = (
                    target_org.owner_id == request.user.id
                    or UserProfile.objects.filter(
                        user=request.user, organization=target_org
                    ).exists()
                )
                if not is_member:
                    return JsonResponse(
                        {"error": "You don't belong to this organization"}, status=403
                    )
                agent.organization = target_org
                agent.user = None

            # Invalidate cache for the old org too (members no longer see it)
            if old_org and old_org != agent.organization:
                _invalidate_agent_cache_for_user_and_org(request.user, old_org)

        serializer = AgentSerializer(agent, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()

            # Invalidar el caché después de actualizar
            _invalidate_agent_cache_for_user_and_org(request.user, agent.organization)

            return JsonResponse(serializer.data, status=200)
        return JsonResponse(serializer.errors, status=400)

    def post(self, request, *args, **kwargs):
        data = JSONParser().parse(request)

        serializer = AgentSerializer(data=data)
        if serializer.is_valid():
            serializer.save(user=request.user)

            # Invalidar el caché después de crear un nuevo agente
            _invalidate_agent_cache_for_user_and_org(
                request.user,
                serializer.instance.organization if serializer.instance else None,
            )

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
        has_admin_flag, _ = FeatureFlagService.is_feature_enabled(
            "edit-organization-agent",
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
        _invalidate_agent_cache_for_user_and_org(request.user, agent_org)

        return JsonResponse({"message": "Agent deleted successfully"})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
@method_decorator(feature_flag_required("add-llm"), name="dispatch")
class LanguageModelView(View):
    def post(self, request, *args, **kwargs):
        data = JSONParser().parse(request)

        provider_name = str(data.get("provider", "")).strip()
        slug = str(data.get("slug", "")).strip()
        name = str(data.get("name", "")).strip()
        pricing = data.get("pricing")

        if not provider_name or not slug or not name:
            return JsonResponse(
                {"error": "provider, slug and name are required"},
                status=400,
            )

        if pricing is not None and not isinstance(pricing, dict):
            return JsonResponse(
                {"error": "pricing must be a JSON object"},
                status=400,
            )

        provider = AIProvider.objects.filter(name__iexact=provider_name).first()
        if not provider:
            return JsonResponse(
                {"error": f"Provider '{provider_name}' does not exist"},
                status=400,
            )

        if LanguageModel.objects.filter(slug=slug).exists():
            return JsonResponse(
                {"error": f"Language model with slug '{slug}' already exists"},
                status=409,
            )

        create_kwargs = {
            "provider": provider,
            "slug": slug,
            "name": name,
        }
        if pricing is not None:
            create_kwargs["pricing"] = pricing

        model = LanguageModel.objects.create(**create_kwargs)

        user_org = None
        if hasattr(request.user, "profile") and request.user.profile.organization:
            user_org = request.user.profile.organization
        _invalidate_agent_cache_for_user_and_org(request.user, user_org)

        return JsonResponse(LanguageModelSerializer(model).data, status=201)


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


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
@method_decorator(feature_flag_required("agent-task"), name="dispatch")
class AgentTaskView(View):
    """
    Trigger an AgentLoop execution as a background Celery task.

    POST /api/ai-layers/agent-task/conversation/
    Body (JSON):
        - conversation_id (str, required): UUID of the conversation
        - agent_slug (str, required): slug of the Agent to use (derives instructions + model)
        - user_inputs (list, required): list of input objects, e.g.
              [{"type": "input_text", "text": "Hello"}]
              Future: input_image, input_document, etc.
        - tool_names (list[str], optional): tool names from the registry (default [])

    The agent's system prompt and LLM model are resolved from the Agent model.
    Messages are always saved to the conversation.

    Returns 202 Accepted with {"task_id": ..., "status": "accepted"}
    """

    def post(self, request, *args, **kwargs):
        from api.messaging.models import Conversation
        from .tasks import conversation_agent_task
        from .tools import list_available_tools

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        # --- Validate required fields ---
        conversation_id = data.get("conversation_id")
        agent_slug = data.get("agent_slug")
        user_inputs = data.get("user_inputs")

        missing = []
        if not conversation_id:
            missing.append("conversation_id")
        if not agent_slug:
            missing.append("agent_slug")
        if not user_inputs or not isinstance(user_inputs, list):
            missing.append("user_inputs (must be a non-empty list)")

        if missing:
            return JsonResponse(
                {"error": f"Missing required fields: {', '.join(missing)}"},
                status=400,
            )

        # --- Validate user_inputs structure ---
        for i, inp in enumerate(user_inputs):
            if not isinstance(inp, dict) or "type" not in inp:
                return JsonResponse(
                    {"error": f"user_inputs[{i}] must be an object with a 'type' field"},
                    status=400,
                )

        # --- Validate optional tool_names ---
        tool_names = data.get("tool_names", [])

        if not isinstance(tool_names, list):
            return JsonResponse(
                {"error": "tool_names must be a list of strings"},
                status=400,
            )

        available = list_available_tools()
        unknown = [t for t in tool_names if t not in available]
        if unknown:
            return JsonResponse(
                {
                    "error": f"Unknown tools: {', '.join(unknown)}",
                    "available_tools": available,
                },
                status=400,
            )

        # --- Look up agent ---
        user = request.user
        user_org = getattr(getattr(user, "profile", None), "organization", None)

        # Agent must belong to the user or their organization
        from django.db.models import Q
        agent_qs = Agent.objects.filter(slug=agent_slug)
        if user_org:
            agent_qs = agent_qs.filter(Q(user=user) | Q(organization=user_org))
        else:
            agent_qs = agent_qs.filter(user=user)

        agent = agent_qs.first()
        if not agent:
            return JsonResponse(
                {"error": f"Agent '{agent_slug}' not found or not accessible"},
                status=404,
            )

        # Derive instructions and model from the agent
        instructions = agent.format_prompt()
        model = agent.llm.slug if agent.llm else (agent.model_slug or "gpt-4o")

        # --- Validate conversation belongs to the user ---
        try:
            conversation = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return JsonResponse(
                {"error": "Conversation not found"},
                status=404,
            )

        is_owner = conversation.user_id == user.id
        is_org_member = (
            user_org is not None
            and conversation.organization_id is not None
            and conversation.organization_id == user_org.id
        )

        if not is_owner and not is_org_member:
            return JsonResponse(
                {"error": "You don't have access to this conversation"},
                status=403,
            )

        # --- Dispatch Celery task ---
        task = conversation_agent_task.delay(
            conversation_id=str(conversation_id),
            user_inputs=user_inputs,
            tool_names=tool_names,
            instructions=instructions,
            user_id=user.id,
            model=model,
        )

        return JsonResponse(
            {"task_id": task.id, "status": "accepted"},
            status=202,
        )
