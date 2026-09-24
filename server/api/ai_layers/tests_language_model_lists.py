import json

from django.contrib.auth.models import User
from django.test import TestCase

from api.authenticate.models import Organization, Token, UserProfile
from api.ai_layers.models import (
    Agent,
    LanguageModel,
    LanguageModelList,
    LanguageModelListMembership,
    language_models_for_organization,
)
from api.consumption.models import Currency
from api.providers.models import AIProvider


class LanguageModelListTests(TestCase):
    def setUp(self):
        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        self.provider = AIProvider.objects.create(name="OpenAI-lists")
        self.default_model = LanguageModel.objects.create(
            provider=self.provider, slug="gpt-default-list", name="Default Model"
        )
        self.advanced_model = LanguageModel.objects.create(
            provider=self.provider, slug="gpt-advanced-list", name="Advanced Model"
        )
        self.default_list = LanguageModelList.objects.create(
            slug="default", name="default"
        )
        self.advanced_list = LanguageModelList.objects.create(
            slug="advanced", name="advanced"
        )
        LanguageModelListMembership.objects.create(
            list=self.default_list, language_model=self.default_model
        )
        LanguageModelListMembership.objects.create(
            list=self.advanced_list, language_model=self.default_model
        )
        LanguageModelListMembership.objects.create(
            list=self.advanced_list, language_model=self.advanced_model
        )
        self.owner = User.objects.create_user(
            username="lmlist_owner", email="lmlist@e.com", password="x"
        )
        self.org = Organization.objects.create(name="List Org", owner=self.owner)
        profile, _ = UserProfile.objects.get_or_create(user=self.owner)
        profile.organization = self.org
        profile.is_active = True
        profile.save()
        self.token = Token.objects.create(user=self.owner)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

    def test_new_organization_gets_default_list(self):
        self.assertEqual(self.org.language_model_list_id, self.default_list.id)

    def test_organization_list_filters_models(self):
        slugs = set(
            language_models_for_organization(self.org).values_list("slug", flat=True)
        )
        self.assertEqual(slugs, {"gpt-default-list"})
        self.org.language_model_list = self.advanced_list
        self.org.save(update_fields=["language_model_list"])
        slugs = set(
            language_models_for_organization(self.org).values_list("slug", flat=True)
        )
        self.assertEqual(slugs, {"gpt-default-list", "gpt-advanced-list"})

    def test_agents_list_returns_organization_models(self):
        res = self.client.get("/v1/ai_layers/agents/", **self.auth)
        self.assertEqual(res.status_code, 200, res.content)
        slugs = {m["slug"] for m in res.json()["models"]}
        self.assertEqual(slugs, {"gpt-default-list"})

    def test_put_rejects_model_outside_organization_list(self):
        agent = Agent.objects.create(
            name="List Agent",
            salute="Hi",
            user=self.owner,
            llm=self.default_model,
        )
        res = self.client.put(
            f"/v1/ai_layers/agents/{agent.slug}/",
            data=json.dumps(
                {
                    "name": agent.name,
                    "salute": agent.salute,
                    "llm": {
                        "slug": "gpt-advanced-list",
                        "provider": "OpenAI-lists",
                    },
                }
            ),
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(res.status_code, 400, res.content)

    def test_upsert_replaces_model_lists(self):
        from api.ai_layers.actions import _upsert_language_model

        payload = {
            "name": "Sync Model",
            "slug": "gpt-sync-list",
            "lists": ["default"],
            "is_reasoning_model": False,
            "pricing": {
                "text": {
                    "prompt": "1.00 USD / 1000000",
                    "output": "1.00 USD / 1000000",
                }
            },
        }
        model = _upsert_language_model(self.provider, payload, "OpenAI")
        self.assertEqual(
            set(model.lists.values_list("slug", flat=True)), {"default"}
        )
        payload["lists"] = ["advanced"]
        model = _upsert_language_model(self.provider, payload, "OpenAI")
        self.assertEqual(
            set(model.lists.values_list("slug", flat=True)), {"advanced"}
        )

    def test_sync_drops_models_missing_from_code_and_fills_null_agents(self):
        from api.ai_layers.actions import sync_language_models_and_agents
        from api.ai_layers.models import Agent

        kept = LanguageModel.objects.create(
            provider=self.provider, slug="gpt-6-luna", name="GPT-6 Luna"
        )
        LanguageModelListMembership.objects.create(
            list=self.default_list, language_model=kept
        )
        LanguageModel.objects.create(
            provider=self.provider, slug="retired-model", name="Retired"
        )
        agent = Agent.objects.create(
            name="No Model Agent",
            salute="Hi",
            user=self.owner,
            llm=kept,
        )
        Agent.objects.filter(pk=agent.pk).update(llm=None, model_slug="")

        result = sync_language_models_and_agents()

        self.assertFalse(LanguageModel.objects.filter(slug="retired-model").exists())
        self.assertTrue(LanguageModel.objects.filter(slug="gpt-6-luna").exists())
        self.assertGreaterEqual(result["removed"], 1)
        agent.refresh_from_db()
        self.assertEqual(agent.llm_id, kept.id)
        self.assertEqual(agent.model_slug, "gpt-6-luna")
