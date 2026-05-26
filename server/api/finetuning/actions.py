import math

from django.db.models import Q
from pydantic import BaseModel, Field

from api.ai_layers.models import Agent
from api.messaging.models import Conversation
from api.rag.models import Document
from api.utils.color_printer import printer
from api.utils.openai_functions import create_structured_completion

from .models import Completion, CompletionAssignment, TrainingGenerator
from .serializers import CompletionSerializer


def _agents_from_slugs(slugs: list[str]) -> list[Agent]:
    agents: list[Agent] = []
    for slug in slugs:
        try:
            agents.append(Agent.objects.get(slug=slug))
        except Agent.DoesNotExist:
            printer.error(f"AGENT {slug} NOT FOUND")
    return agents


def _merged_target_description(agents: list[Agent]) -> str:
    blocks = []
    for agent in agents:
        blocks.append(
            f"""### Agent: {agent.name} (slug={agent.slug})
```txt agent.act_as
{agent.act_as}
```
```txt agent.system_prompt
{agent.system_prompt}
```
"""
        )
    return "\n".join(blocks)


def create_training_generator(data, user):
    printer.green("generate_training_completions")

    db_model = data.get("db_model")
    model_id = data.get("model_id")
    agents = data.get("agents")
    completions_target_number = data.get("completions_target_number")
    only_prompt = data.get("only_prompt")

    if db_model == "conversation":
        conversation = Conversation.objects.get(id=model_id)
        if not conversation:
            raise Exception("Conversation not found")
        create_generator_for_conversation(
            conversation, agents, completions_target_number, only_prompt, user
        )

    if db_model == "document":
        document = Document.objects.get(id=model_id)
        if not document:
            raise Exception("Document not found")

        create_generator_for_document(
            document, agents, completions_target_number, only_prompt, user
        )


def create_generator_for_conversation(
    conversation, agents, completions_target_number, only_prompt, user
):
    agent_objs = _agents_from_slugs(agents)
    if not agent_objs:
        return

    names = ", ".join(a.name for a in agent_objs)
    generator = TrainingGenerator.objects.create(
        name=f"Training for {names} on conversation {conversation.title}"[:255],
        completions_target_number=completions_target_number,
        target_model_description=_merged_target_description(agent_objs),
        only_prompt=only_prompt,
        created_by=user,
        source_text=conversation.get_all_messages_context(),
    )
    generator.agents.set(agent_objs)


def create_generator_for_document(
    document, agents, completions_target_number, only_prompt, user
):
    printer.yellow(
        f"TRYING TO GENERATE COMPLETIONS FOR A DOCUMENT: {document.total_tokens} TOKENS"
    )
    if document.total_tokens > 80000:
        printer.yellow(
            f"DOCUMENT TOO LARGE, dividing it into {document.total_tokens / 80000} parts"
        )
        parts = math.ceil(document.total_tokens / 80000)
    else:
        parts = 1

    agent_objs = _agents_from_slugs(agents)
    if not agent_objs:
        return

    names = ", ".join(a.name for a in agent_objs)
    for i in range(parts):
        tg_name = f"Training for {names} on document {document.name} - part {i + 1}"[:255]
        generator = TrainingGenerator.objects.create(
            name=tg_name,
            completions_target_number=completions_target_number,
            target_model_description=_merged_target_description(agent_objs),
            only_prompt=only_prompt,
            created_by=user,
            source_text=document.text[i * 80000 : (i + 1) * 80000],
        )
        generator.agents.set(agent_objs)


class CompletionData(BaseModel):
    prompt: str = Field(
        description="The prompt for the completion, ex: What is the middle of the east?, another example: Name of the capital of the moon, keep in mind that the agent is a human, so the prompt should be a question or a statement that a human would say"
    )
    answer: str = Field(
        description="The answer for the completion, ex: The middle of the east is a place in the world, the capital of the moon is called New Moon. Obvously, the answer should be in the same language as the prompt and the source text. And it must be related to the source text"
    )


class GeneratorResponse(BaseModel):
    completions: list[CompletionData] = Field(
        description="The generated completions to train the specified agents"
    )


def start_generator(generator_id):
    printer.green(f"STARTING GENERATOR {generator_id}")
    generator = TrainingGenerator.objects.prefetch_related("agents").get(id=generator_id)

    if not generator:
        raise Exception("Generator not found")

    agent_ids = list(generator.agents.values_list("id", flat=True))
    if not agent_ids:
        printer.error(f"Generator {generator_id} has no agents assigned")
        return False

    response = create_structured_completion(
        model="gpt-4o-mini",
        system_prompt=generator.get_system_prompt(),
        response_format=GeneratorResponse,
        user_prompt="Generate completions for the agents",
    )

    completion_rows = [
        Completion(
            prompt=completion.prompt,
            answer=completion.answer,
            training_generator=generator,
        )
        for completion in response.completions
    ]
    created = Completion.objects.bulk_create(completion_rows)

    assignments = [
        CompletionAssignment(completion=completion, agent_id=agent_id)
        for completion in created
        for agent_id in agent_ids
    ]
    CompletionAssignment.objects.bulk_create(assignments, ignore_conflicts=True)

    printer.green(
        f"GENERATED {len(created)} COMPLETIONS with assignments for {len(agent_ids)} agent(s)"
    )
    return True


def _accessible_completions_qs(user):
    from api.ai_layers.access import get_user_organization

    user_org = get_user_organization(user)
    base = Completion.objects.prefetch_related("assignments")
    if user_org:
        return base.filter(
            Q(assignments__agent__user=user)
            | Q(assignments__agent__organization=user_org)
        ).distinct()
    return base.filter(assignments__agent__user=user).distinct()


def get_user_completions(user):
    completions = _accessible_completions_qs(user)
    return CompletionSerializer(completions, many=True).data
