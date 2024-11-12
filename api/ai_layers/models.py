from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from api.providers.models import AIProvider
from api.utils.openai_functions import create_structured_completion
from pydantic import BaseModel, Field
from datetime import datetime


class ExampleStructure(BaseModel):
    example: str = Field(description="An example of a good response")


DEFAULT_CHARACTER = """
You are an useful assistant.
"""

DEFAULT_SYSTEM_PROMPT = """
{{act_as}}

The following context may be useful for your task:
```
{{context}}
```
"""


class LanguageModel(models.Model):
    provider = models.ForeignKey(AIProvider, on_delete=models.CASCADE)
    slug = models.CharField(max_length=100, unique=True, blank=True)
    name = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.provider.name})"


class Agent(models.Model):

    MODEL_PROVIDER_CHOICES = [
        ("openai", "OpenAI"),
        ("ollama", "Ollama"),
        ("anthropic", "Anthropic"),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    model_slug = models.CharField(
        max_length=100, default="gpt-4o-mini", null=True, blank=True
    )
    llm = models.ForeignKey(
        LanguageModel, on_delete=models.SET_NULL, null=True, blank=True
    )

    model_provider = models.CharField(
        max_length=20, choices=MODEL_PROVIDER_CHOICES, default="openai"
    )
    system_prompt = models.TextField(default=DEFAULT_SYSTEM_PROMPT)

    salute = models.TextField()
    act_as = models.TextField(
        default=DEFAULT_CHARACTER, help_text="How should the AI act?"
    )

    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, null=True, blank=True
    )

    is_public = models.BooleanField(default=False)
    default = models.BooleanField(default=False)
    temperature = models.FloatField(
        validators=[MinValueValidator(0.00), MaxValueValidator(2.00)], default=0.7
    )
    max_tokens = models.IntegerField(null=True, blank=True, default=4000)
    top_p = models.FloatField(
        validators=[MinValueValidator(0.00), MaxValueValidator(1.00)], default=1.00
    )
    frequency_penalty = models.FloatField(
        validators=[MinValueValidator(-2.00), MaxValueValidator(2.00)], default=0
    )
    presence_penalty = models.FloatField(
        validators=[MinValueValidator(-2.00), MaxValueValidator(2.00)], default=0
    )
    profile_picture_url = models.URLField(null=True, blank=True, max_length=500)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from .tasks import async_generate_agent_profile_picture
        if not self.slug:
            self.slug = slugify(self.name)

        if not self.llm:
            llm = LanguageModel.objects.get(slug=self.model_slug)
            self.llm = llm

        if not self.profile_picture_url:
            async_generate_agent_profile_picture.delay(self.id)
            
        super().save(*args, **kwargs)

    def format_prompt(self, context: str = ""):
        formatted = self.system_prompt.replace("{{act_as}}", self.act_as).replace(
            "{{context}}", context
        )
        return formatted

    def answer(
        self,
        context: str = "",
        user_message: str = "Hello, who are you?",
        response_format: BaseModel = ExampleStructure,
    ):
        context, sources = self.append_rag_context(context)
        _system = self.format_prompt(context=context)

        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        _system += f"\nThe current date and time is {current_datetime} in you need to use it in your response"
        response = create_structured_completion(
            system_prompt=_system,
            user_prompt=user_message,
            model="gpt-4o-mini",
            response_format=response_format,
        )

        return response

    def serialize(self):
        from .serializers import AgentSerializer

        serializer = AgentSerializer(self)
        return serializer.data

    def get_collection(self):
        from api.rag.models import Collection

        return Collection.objects.get(agent=self)

    def append_rag_context(self, context: str = ""):
        from api.rag.managers import chroma_client
        from api.rag.actions import querify_context, extract_rag_results

        collection = self.get_collection()
        queries = querify_context(context)
        results = chroma_client.get_results(
            collection_name=collection.slug,
            query_texts=queries.queries,
            n_results=3,
        )

        return extract_rag_results({"results": results}, context)
    
    # def generate_profile_picture(self):
        
        
