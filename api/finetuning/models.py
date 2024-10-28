from django.db import models
from django.contrib.auth.models import User

from api.ai_layers.models import Agent


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
    name = models.CharField(max_length=100)
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
