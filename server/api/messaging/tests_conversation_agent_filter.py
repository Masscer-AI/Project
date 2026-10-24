from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.ai_layers.models import LanguageModel
from api.authenticate.models import Token
from api.consumption.models import Currency
from api.messaging.models import Conversation, Message
from api.providers.models import AIProvider


def _bootstrap():
    Currency.objects.get_or_create(name="Compute Unit", defaults={"one_usd_is": 1000})
    provider, _ = AIProvider.objects.get_or_create(name="Agent Filter Provider")
    LanguageModel.objects.get_or_create(
        slug="agent-filter-model",
        defaults={"provider": provider, "name": "Agent Filter Model"},
    )


class ConversationAgentFilterTests(TestCase):
    def setUp(self):
        _bootstrap()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="agent-filter-user",
            email="agent-filter@example.com",
            password="pass-123456",
        )
        self.token = Token.objects.create(user=self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

    def _conversation(self, title, agent_ids):
        conversation = Conversation.objects.create(
            user=self.user,
            title=title,
            metadata={"related_agents": [{"id": agent_id} for agent_id in agent_ids]},
        )
        Message.objects.create(conversation=conversation, type="user", text="hello")
        return conversation

    def _listed_titles(self, agents):
        response = self.client.get(
            "/v1/messaging/conversations",
            {"scope": "personal", "status": "all", "agents": agents},
            **self.auth,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return {row["title"] for row in response.json()["results"]}

    def test_agents_query_filters_related_agents(self):
        self._conversation("Only eleven", [11])
        self._conversation("Only twenty two", [22])
        self._conversation("Both", [11, 22])
        self._conversation("None", [])

        self.assertEqual(self._listed_titles("11"), {"Only eleven", "Both"})
        self.assertEqual(
            self._listed_titles("11,22"),
            {"Only eleven", "Only twenty two", "Both"},
        )
        self.assertEqual(self._listed_titles("99"), set())
