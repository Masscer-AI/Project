"""Tests for admin LLM fill of Agent.description."""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from api.ai_layers.models import Agent, LanguageModel
from api.authenticate.models import Organization, UserProfile
from api.consumption.models import Currency
from api.providers.models import AIProvider


def _seed_llm():
    Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
    provider = AIProvider.objects.create(
        name=f"OpenAI-desc-{LanguageModel.objects.count()}"
    )
    return LanguageModel.objects.create(
        provider=provider,
        slug=f"gpt-desc-{LanguageModel.objects.count()}",
        name="GPT Desc",
        pricing={
            "text": {
                "prompt": "2.50 USD / 1000000",
                "output": "10 USD / 1000000",
            }
        },
    )


class FillEmptyAgentDescriptionTests(TestCase):
    def setUp(self):
        _seed_llm()
        self.user = User.objects.create_user(username="desc-owner", password="x")
        self.org = Organization.objects.create(name="Desc Org", owner=self.user)
        UserProfile.objects.get_or_create(
            user=self.user, defaults={"organization": self.org}
        )
        self.agent = Agent.objects.create(
            name="Tax Helper",
            slug="tax-helper-desc",
            salute="hi",
            act_as="You help Mexican companies with SAT and tax compliance.",
            description="",
            user=self.user,
            organization=self.org,
        )

    @patch("api.consumption.actions.register_llm_interaction")
    @patch("openai.OpenAI")
    def test_fills_and_bills_org(self, mock_openai, mock_register):
        completion = MagicMock()
        completion.usage.input_tokens = 40
        completion.usage.output_tokens = 25
        completion.output_text = (
            '{"description": "Handles SAT and tax compliance for Mexican companies."}'
        )
        mock_openai.return_value.responses.create.return_value = completion

        from api.ai_layers.agent_description import fill_empty_agent_description

        result = fill_empty_agent_description(
            self.agent, billing_user_id=self.user.id
        )

        self.agent.refresh_from_db()
        self.assertEqual(
            result,
            "Handles SAT and tax compliance for Mexican companies.",
        )
        self.assertEqual(self.agent.description, result)
        mock_register.assert_called_once_with(
            self.user.id,
            40,
            25,
            "gpt-5.6-luna",
            organization_id=self.org.id,
        )

    def test_skips_when_description_already_set(self):
        self.agent.description = "Already filled"
        self.agent.save(update_fields=["description"])
        from api.ai_layers.agent_description import fill_empty_agent_description

        self.assertIsNone(fill_empty_agent_description(self.agent))

    def test_requires_organization(self):
        self.agent.organization = None
        self.agent.save(update_fields=["organization"])
        from api.ai_layers.agent_description import fill_empty_agent_description

        with self.assertRaises(ValueError) as ctx:
            fill_empty_agent_description(self.agent, billing_user_id=self.user.id)
        self.assertIn("no organization", str(ctx.exception).lower())

    @patch("api.consumption.actions.register_llm_interaction")
    @patch("openai.OpenAI")
    def test_regenerate_overwrites_existing(self, mock_openai, mock_register):
        self.agent.description = "Old description"
        self.agent.save(update_fields=["description"])
        completion = MagicMock()
        completion.usage.input_tokens = 10
        completion.usage.output_tokens = 8
        completion.output_text = '{"description": "Fresh specialty blurb."}'
        mock_openai.return_value.responses.create.return_value = completion

        from api.ai_layers.agent_description import regenerate_agent_description

        result = regenerate_agent_description(
            self.agent, billing_user_id=self.user.id
        )
        self.agent.refresh_from_db()
        self.assertEqual(result, "Fresh specialty blurb.")
        self.assertEqual(self.agent.description, result)
