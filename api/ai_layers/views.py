from django.views import View
import json
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Q
from .models import Agent, LanguageModel, AgentSession
from .serializers import AgentSerializer, LanguageModelSerializer, AgentSessionSerializer
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


def _invalidate_agent_cache_for_user_and_org(user, agent_organization=None):
    """
    Invalidate agent cache so updated agent data is reflected on next fetch.

    The GET endpoint uses cache key agent_data_{user_id}_{org_id} where org_id
    comes from the REQUESTING user's profile (their org or "no_org"), not the
    agent's. So we must invalidate using the requester's org.

    - For the requester: invalidate BOTH no_org and their org (covers personal
      agents when user has org, and org agents).
    - For org agents: also invalidate all org members (they see org agents).
    """
    # Always invalidate requester's possible cache keys
    cache.delete(f"agent_data_{user.id}_no_org")
    user_org = getattr(getattr(user, "profile", None), "organization", None)
    if user_org:
        cache.delete(f"agent_data_{user.id}_{user_org.id}")

    if not agent_organization:
        return

    # Org agent changed: invalidate for all org members
    org_members = User.objects.filter(
        Q(profile__organization=agent_organization) | Q(id=agent_organization.owner_id)
    ).distinct()
    for member in org_members:
        cache.delete(f"agent_data_{member.id}_{agent_organization.id}")


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
@method_decorator(feature_flag_required("manage-llm"), name="dispatch")
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

    def delete(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        if not slug:
            return JsonResponse(
                {"error": "Model slug is required in the URL"},
                status=400,
            )

        try:
            model = LanguageModel.objects.select_related("provider").get(slug=slug)
        except LanguageModel.DoesNotExist:
            return JsonResponse(
                {"error": f"Language model '{slug}' not found"},
                status=404,
            )

        # Auto-migrate agents using this LLM to another LLM of the same provider
        affected_agents = Agent.objects.filter(llm=model)
        replacement = (
            LanguageModel.objects.filter(provider=model.provider)
            .exclude(id=model.id)
            .first()
        )

        migrated_count = 0
        if affected_agents.exists():
            if not replacement:
                return JsonResponse(
                    {
                        "error": f"Cannot delete '{slug}': {affected_agents.count()} agent(s) use it "
                        f"and no other model exists for provider '{model.provider.name}' to migrate to."
                    },
                    status=409,
                )
            migrated_count = affected_agents.update(llm=replacement)

        model_name = model.name
        model.delete()

        user_org = None
        if hasattr(request.user, "profile") and request.user.profile.organization:
            user_org = request.user.profile.organization
        _invalidate_agent_cache_for_user_and_org(request.user, user_org)

        return JsonResponse(
            {
                "status": "deleted",
                "deleted": model_name,
                "migrated_agents": migrated_count,
                "migrated_to": replacement.slug if replacement and migrated_count else None,
            }
        )


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
    model_slug = random.choice(["gpt-4o-mini", "gpt-4o"])
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
        - agent_slugs (list[str], required): slugs of one or more Agents
        - user_inputs (list, required): list of input objects, e.g.
              [{"type": "input_text", "text": "Hello"}]
        - tool_names (list[str], optional): tool names from the registry (default [])
        - multiagentic_modality (str, optional): "isolated" or "grupal" (default "isolated")

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
        agent_slugs = data.get("agent_slugs")
        user_inputs = data.get("user_inputs")

        if not isinstance(agent_slugs, list):
            return JsonResponse(
                {"error": "agent_slugs must be a list of strings"},
                status=400,
            )
        slugs = [s for s in agent_slugs if isinstance(s, str) and s.strip()]

        missing = []
        if not conversation_id:
            missing.append("conversation_id")
        if not slugs:
            missing.append("agent_slugs (at least one agent required)")
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

        multiagentic_modality = data.get("multiagentic_modality", "isolated")
        if multiagentic_modality not in ("isolated", "grupal"):
            return JsonResponse(
                {"error": "multiagentic_modality must be 'isolated' or 'grupal'"},
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

        # --- Look up agents ---
        user = request.user
        user_org = getattr(getattr(user, "profile", None), "organization", None)

        from django.db.models import Q
        base_qs = Agent.objects.all()
        if user_org:
            base_qs = base_qs.filter(Q(user=user) | Q(organization=user_org))
        else:
            base_qs = base_qs.filter(user=user)

        agents_found = list(base_qs.filter(slug__in=slugs))
        found_slugs = {a.slug for a in agents_found}
        not_found = [s for s in slugs if s not in found_slugs]
        if not_found:
            return JsonResponse(
                {"error": f"Agent(s) not found or not accessible: {', '.join(not_found)}"},
                status=404,
            )

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
            agent_slugs=slugs,
            multiagentic_modality=multiagentic_modality,
            user_id=user.id,
        )

        return JsonResponse(
            {"task_id": task.id, "status": "accepted"},
            status=202,
        )


def _user_can_access_message(user, message):
    """Check if user can access the message's conversation."""
    from api.messaging.models import Message
    from api.authenticate.models import Organization

    conv = message.conversation
    if not conv:
        return False
    if conv.user_id == user.id:
        return True
    org_user_ids = []
    owned_orgs = Organization.objects.filter(owner=user)
    if hasattr(user, "profile") and user.profile.organization_id:
        member_orgs = Organization.objects.filter(id=user.profile.organization_id)
        orgs = (owned_orgs | member_orgs).distinct()
    else:
        orgs = owned_orgs
    if orgs.exists():
        owner_ids = set(
            Organization.objects.filter(id__in=orgs).values_list("owner_id", flat=True)
        )
        member_ids = set(
            User.objects.filter(
                profile__organization__in=orgs
            ).values_list("id", flat=True)
        )
        org_user_ids = list(owner_ids | member_ids)
    if org_user_ids and (
        conv.user_id in org_user_ids or conv.user_id is None
    ):
        return True
    return False


@csrf_exempt
@token_required
def agent_sessions_for_message(request):
    """
    GET /api/ai_layers/agent-sessions/?assistant_message_id=123
    Returns AgentSessions for the given assistant message, ordered by agent_index.
    User must have access to the message's conversation.
    """
    from api.messaging.models import Message

    msg_id = request.GET.get("assistant_message_id")
    if not msg_id:
        return JsonResponse(
            {"error": "assistant_message_id is required"}, status=400
        )
    try:
        msg_id = int(msg_id)
    except (TypeError, ValueError):
        return JsonResponse({"error": "assistant_message_id must be an integer"}, status=400)

    try:
        message = Message.objects.get(id=msg_id)
    except Message.DoesNotExist:
        return JsonResponse({"error": "Message not found"}, status=404)

    if not _user_can_access_message(request.user, message):
        return JsonResponse({"error": "Forbidden"}, status=403)

    sessions = AgentSession.objects.filter(
        assistant_message_id=msg_id
    ).order_by("agent_index")

    data = AgentSessionSerializer(sessions, many=True).data
    return JsonResponse(data, safe=False)
