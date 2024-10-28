from api.utils.color_printer import printer
from api.messaging.models import Conversation
from .models import TrainingGenerator, Completion
from api.ai_layers.models import Agent
from api.utils.openai_functions import create_structured_completion
from pydantic import BaseModel, Field


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


def create_generator_for_conversation(
    conversation, agents, completions_target_number, only_prompt, user
):
    for a in agents:
        agent = Agent.objects.get(slug=a)
        if not agent:
            printer.error(f"AGENT {a} NOT FOUND")
            continue

        _description = f"""
This is how the user described the agent character:
```txt agent.act_as
{agent.act_as}
```
This is the system prompt of the agent:

```txt agent.system_prompt

{agent.system_prompt}
```
"""

        TrainingGenerator.objects.create(
            name=f"Training for {agent.name} on conversation {conversation.title}",
            agent=agent,
            completions_target_number=completions_target_number,
            target_model_description=_description,
            only_prompt=only_prompt,
            created_by=user,
            source_text=conversation.get_all_messages_context(),
        )


class CompletionData(BaseModel):
    prompt: str = Field(description="The prompt for the completion")
    answer: str = Field(description="The answer for the completion")


class GeneratorResponse(BaseModel):
    completions: list[CompletionData] = Field(
        description="The generated completions to train the specified agent"
    )


def start_generator(generator_id):
    printer.green(f"STARTING GENERATOR {generator_id}")
    generator = TrainingGenerator.objects.get(id=generator_id)

    if not generator:
        raise Exception("Generator not found")

    response = create_structured_completion(
        model="gpt-4o-mini",
        system_prompt=generator.get_system_prompt(),
        response_format=GeneratorResponse,
        user_prompt="Generate completions for the agent",
    )
    # BULK CREATE COMPLETIONS
    completions = [
        Completion(
            prompt=completion.prompt,
            answer=completion.answer,
            training_generator=generator,
            agent=generator.agent,
        )
        for completion in response.completions
    ]
    Completion.objects.bulk_create(completions)
    printer.green(f"GENERATED {len(completions)} COMPLETIONS")
