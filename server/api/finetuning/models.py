from django.db import models
from django.contrib.auth.models import User

from api.ai_layers.models import Agent
from api.rag.managers import chroma_client
from api.rag.models import Collection
from api.utils.color_printer import printer

from .context_rules import default_context_rules_dict


class TrainingGenerator(models.Model):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    STATUSES = (
        (PENDING, "Pending"),
        (GENERATING, "Generating"),
        (COMPLETED, "Completed"),
    )

    DEFAULT_GENERATION_PROMPT = """
You are an specialist machine learning engineer.
You are in charge of generating a set of {completions_target_number} completions to train an AI model.

After the finetuning or  training process the target model should be like:
---
{target_model_description}
---


Use this text as a source of information to generate the completions:
---
{source_text}
---

only_prompt = {only_prompt}

If the variable only_prompt is True, then you must generate only the prompt for each completion, otherwise generate the prompt and the answer.


CLARIFICATION:
The goal is to optain a list of different completions based in the source text. Each prompt/answer pair must be different from the others.
"""
    name = models.CharField(max_length=255)
    completions_target_number = models.IntegerField(default=30)
    target_model_description = models.TextField()
    source_text = models.TextField()
    generation_prompt = models.TextField(default=DEFAULT_GENERATION_PROMPT)
    agents = models.ManyToManyField(
        Agent,
        related_name="training_generators",
        blank=True,
    )
    only_prompt = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="training_generators",
    )
    status = models.CharField(max_length=255, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Training Generator {self.name}"

    def get_system_prompt(self):
        return self.generation_prompt.format(
            completions_target_number=self.completions_target_number,
            target_model_description=self.target_model_description,
            source_text=self.source_text,
            only_prompt=self.only_prompt,
        )


class Completion(models.Model):
    prompt = models.TextField()
    answer = models.TextField()
    context_rules = models.JSONField(default=default_context_rules_dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_completions",
    )

    training_generator = models.ForeignKey(
        TrainingGenerator, on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        indexes = [
            models.Index(fields=["approved"]),
        ]

    def __str__(self):
        return f"Completion for prompt: {self.prompt[:50]}..."

    def get_assigned_agents(self):
        return Agent.objects.filter(completion_assignments__completion=self)

    def approve(self, expert_user):
        self.approved = True
        self.approved_by = expert_user
        self.save()

    def _chunk_metadata(self):
        return {
            "content": f"PROMPT: {self.prompt}\n\nANSWER: {self.answer}",
            "model_id": self.id,
            "model_name": "completion",
            "extra": (
                f"TRAINING_GENERATOR(name={self.training_generator.name}, id={self.training_generator.id})"
                if self.training_generator
                else "TRAINING_GENERATOR(None)"
            ),
        }

    def save_in_memory(self):
        printer.yellow(f"Saving completion {self.id} in memory")
        if not chroma_client:
            printer.red("ChromaDB not available, skipping save_in_memory")
            return

        assignments = list(
            self.assignments.select_related("agent").all()
        )
        if not assignments:
            printer.red("Completion has no agent assignments, skipping save_in_memory")
            return

        for assignment in assignments:
            agent = assignment.agent
            collection, created = Collection.get_or_create_agent_collection(agent=agent)
            if created:
                printer.red(
                    f"Collection not found for agent {agent.slug}, creating a new one"
                )

            chroma_client.upsert_chunk(
                collection_name=collection.slug,
                chunk_id=str(self.id) + "-completion",
                chunk_text=self.prompt,
                metadata=self._chunk_metadata(),
            )
        printer.success(f"Completion {self.id} saved in memory for {len(assignments)} agent(s)")

    def remove_from_agent_memory(self, agent):
        if not chroma_client:
            printer.red("ChromaDB not available, skipping remove_from_agent_memory")
            return

        collection, created = Collection.get_or_create_agent_collection(agent=agent)
        if created:
            printer.yellow(
                f"Collection not found for agent {agent.slug} and it was created, skipping removal"
            )
            return

        printer.red(f"Removing completion {self.id} from memory (agent={agent.slug})")
        chroma_client.delete_chunk(
            collection_name=collection.slug,
            chunk_id=str(self.id) + "-completion",
        )

    def remove_from_memory(self):
        if not chroma_client:
            printer.red("ChromaDB not available, skipping remove_from_memory")
            return

        assignments = list(
            self.assignments.select_related("agent").all()
        )
        if not assignments:
            printer.red("Completion has no agent assignments, skipping remove_from_memory")
            return

        for assignment in assignments:
            self.remove_from_agent_memory(assignment.agent)


class CompletionAssignment(models.Model):
    completion = models.ForeignKey(
        Completion,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="completion_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["completion", "agent"],
                name="completion_assignment_unique_completion_agent",
            ),
        ]
        indexes = [
            models.Index(fields=["agent"]),
            models.Index(fields=["completion"]),
        ]

    def __str__(self):
        return f"Completion {self.completion_id} -> Agent {self.agent_id}"
