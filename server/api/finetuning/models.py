from django.db import models
from django.contrib.auth.models import User

from api.ai_layers.models import Agent
from api.rag.managers import chroma_client
from api.rag.models import Collection
from api.utils.color_printer import printer


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
    # organization = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    completions_target_number = models.IntegerField(default=30)
    target_model_description = models.TextField()
    source_text = models.TextField()
    generation_prompt = models.TextField(default=DEFAULT_GENERATION_PROMPT)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True)
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
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True)
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

    def __str__(self):
        return f"Completion for prompt: {self.prompt[:50]}..."

    def approve(self, expert_user):
        self.approved = True
        self.approved_by = expert_user
        self.save()

    def save_in_memory(self):
        printer.yellow(f"Saving completion {self.id} in memory")
        if not chroma_client:
            printer.red("ChromaDB not available, skipping save_in_memory")
            return
        if not self.agent:
            printer.red("Completion has no agent, skipping save_in_memory")
            return

        # Match how chat RAG is scoped: Collection is per (user, agent).
        # Prefer the user who initiated training (training_generator.created_by),
        # then the user who approved it, then fall back to agent owner.
        collection_user = None
        if self.training_generator and getattr(self.training_generator, "created_by_id", None):
            collection_user = self.training_generator.created_by
        elif self.approved_by_id:
            collection_user = self.approved_by
        else:
            collection_user = self.agent.user

        collection, created = Collection.objects.get_or_create(
            agent=self.agent, user=collection_user
        )
        if created:
            printer.red(
                f"Collection not found for agent {self.agent.slug}, creating a new one"
            )

        chroma_client.upsert_chunk(
            collection_name=collection.slug,
            chunk_id=str(self.id) + "-completion",
            chunk_text=self.prompt,
            metadata={
                "content": f"PROMPT: {self.prompt}\n\nANSWER: {self.answer}",
                "model_id": self.id,
                "model_name": "completion",
                "extra": (
                    f"TRAINING_GENERATOR(name={self.training_generator.name}, id={self.training_generator.id})"
                    if self.training_generator
                    else "TRAINING_GENERATOR(None)"
                ),
            },
        )
        printer.success(f"Completion {self.id} saved in memory")

    def remove_from_memory(self):
        if not chroma_client:
            printer.red("ChromaDB not available, skipping remove_from_memory")
            return
        if not self.agent:
            printer.red("Completion has no agent, skipping remove_from_memory")
            return

        collection_user = None
        if self.training_generator and getattr(self.training_generator, "created_by_id", None):
            collection_user = self.training_generator.created_by
        elif self.approved_by_id:
            collection_user = self.approved_by
        else:
            collection_user = self.agent.user

        collection, created = Collection.objects.get_or_create(
            agent=self.agent, user=collection_user
        )
        if created:
            printer.yellow(
                f"Collection not found for agent {self.agent.slug} and it was created, skipping removal"
            )
            return

        printer.red(f"Removing completion {self.id} from memory")
        chroma_client.delete_chunk(
            collection_name=collection.slug, chunk_id=str(self.id) + "-completion"
        )
