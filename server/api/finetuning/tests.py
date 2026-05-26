from django.contrib.auth.models import User
from django.test import TestCase

from api.ai_layers.models import Agent, LanguageModel
from api.messaging.models import Conversation
from api.providers.models import AIProvider

from .context_injection import (
    completion_matches_context_rules,
    format_completions_context_block,
    get_completions_for_context,
)
from .context_rules import CompletionContextRules, validate_context_rules_for_storage
from .models import Completion, CompletionAssignment


class CompletionContextRulesTests(TestCase):
    def test_validate_context_rules_for_storage(self):
        stored = validate_context_rules_for_storage(
            {"include_always": True, "include_for_tags": [1, 2]}
        )
        self.assertEqual(stored["include_always"], True)
        self.assertEqual(stored["include_for_tags"], [1, 2])

    def test_validate_rejects_unknown_keys(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            CompletionContextRules.model_validate({"foo": True})


class CompletionAssignmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ftu", email="ftu@e.com", password="x")
        provider = AIProvider.objects.create(name="OpenAI-ft")
        llm = LanguageModel.objects.create(provider=provider, slug="gpt-ft", name="GPT")
        self.agent_a = Agent.objects.create(
            name="A",
            salute="h",
            act_as="a",
            user=self.user,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )
        self.agent_b = Agent.objects.create(
            name="B",
            salute="h",
            act_as="b",
            user=self.user,
            llm=llm,
            model_slug=llm.slug,
            model_provider="openai",
        )

    def test_context_injection_include_always(self):
        conv = Conversation.objects.create(user=self.user, tags=[99])
        completion = Completion.objects.create(
            prompt="cue",
            answer="payload",
            approved=True,
            context_rules={"include_always": True, "include_for_tags": []},
        )
        CompletionAssignment.objects.create(completion=completion, agent=self.agent_a)

        matched = get_completions_for_context(self.agent_a, conv)
        self.assertEqual(len(matched), 1)
        block = format_completions_context_block(matched)
        self.assertIn("AGENT TRAINING", block)
        self.assertIn("payload", block)

    def test_context_injection_include_for_tags(self):
        conv = Conversation.objects.create(user=self.user, tags=[5, 9])
        completion = Completion.objects.create(
            prompt="cue",
            answer="payload",
            approved=True,
            context_rules={"include_always": False, "include_for_tags": [9]},
        )
        CompletionAssignment.objects.create(completion=completion, agent=self.agent_a)

        self.assertTrue(completion_matches_context_rules(completion, conv))
        self.assertEqual(len(get_completions_for_context(self.agent_a, conv)), 1)

        conv.tags = [1]
        conv.save(update_fields=["tags"])
        self.assertFalse(completion_matches_context_rules(completion, conv))

    def test_unassigned_agent_gets_no_injection(self):
        conv = Conversation.objects.create(user=self.user)
        completion = Completion.objects.create(
            prompt="cue",
            answer="payload",
            approved=True,
            context_rules={"include_always": True, "include_for_tags": []},
        )
        CompletionAssignment.objects.create(completion=completion, agent=self.agent_a)

        self.assertEqual(len(get_completions_for_context(self.agent_b, conv)), 0)
