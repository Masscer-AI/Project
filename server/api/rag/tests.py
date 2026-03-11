from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase

from api.ai_layers.models import Agent, LanguageModel
from api.ai_layers.tools.rag_query import _rag_query_impl
from api.finetuning.models import Completion
from api.providers.models import AIProvider
from api.rag.models import Collection


class SharedAgentRagTests(TestCase):
    def setUp(self):
        self.rag_chroma_patch = patch("api.rag.models.chroma_client", None)
        self.rag_chroma_patch.start()

        self.provider = AIProvider.objects.create(name="OpenAI")
        self.llm = LanguageModel.objects.create(
            provider=self.provider,
            name="Test LLM",
            slug="test-llm",
        )
        self.owner = User.objects.create_user(username="owner", password="x")
        self.other_user = User.objects.create_user(username="other", password="x")
        self.agent = Agent.objects.create(
            name="Agent A",
            salute="hello",
            user=self.owner,
            llm=self.llm,
            model_slug=self.llm.slug,
            is_public=True,
        )

    def tearDown(self):
        self.rag_chroma_patch.stop()

    def test_collection_enforces_exactly_one_owner(self):
        with self.assertRaises(IntegrityError):
            Collection.objects.create(name="invalid-both", user=self.owner, agent=self.agent)

        with self.assertRaises(IntegrityError):
            Collection.objects.create(name="invalid-none", user=None, agent=None)

    def test_completion_saves_in_shared_agent_collection(self):
        completion = Completion.objects.create(
            prompt="prompt",
            answer="answer",
            agent=self.agent,
            approved_by=self.owner,
        )

        with patch("api.finetuning.models.chroma_client") as mocked_chroma:
            completion.save_in_memory()
            mocked_chroma.upsert_chunk.assert_called_once()

        collection = Collection.objects.get(agent=self.agent, user=None)
        self.assertIsNotNone(collection)
        self.assertEqual(
            Collection.objects.filter(agent=self.agent, user=None).count(),
            1,
        )

    def test_rag_query_reads_only_agent_collection(self):
        shared_collection, _ = Collection.get_or_create_agent_collection(agent=self.agent)
        Collection.get_or_create_personal_collection(user=self.other_user)

        with patch("api.rag.managers.chroma_client") as mocked_chroma:
            mocked_chroma.get_results.return_value = {
                "ids": [],
                "metadatas": [],
                "documents": [],
                "distances": [],
            }
            _rag_query_impl(
                user_id=self.other_user.id,
                agent_slug=self.agent.slug,
                queries=["what is this?"],
                n_results=3,
            )

            mocked_chroma.get_results.assert_called_once()
            self.assertEqual(
                mocked_chroma.get_results.call_args.kwargs["collection_name"],
                shared_collection.slug,
            )
