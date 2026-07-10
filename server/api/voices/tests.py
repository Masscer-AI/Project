from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from api.authenticate.models import Organization
from api.voices.access import (
    get_default_system_voice,
    get_voice_by_id,
    resolve_accessible_voices,
    resolve_voice_for_speech,
)
from api.voices.constants import DEFAULT_OPENAI_VOICE_ID
from api.voices.models import Voice, VoiceProvider, VoiceScope


class VoiceModelTests(TestCase):
    def test_system_voice_invariants(self):
        voice = Voice(
            name="Coral",
            slug="coral",
            provider=VoiceProvider.OPENAI,
            provider_voice_id="coral",
            scope=VoiceScope.SYSTEM,
        )
        voice.full_clean()
        voice.save()
        self.assertEqual(Voice.objects.filter(scope=VoiceScope.SYSTEM).count(), 1)

    def test_user_voice_requires_user(self):
        voice = Voice(
            name="Custom",
            slug="custom",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="abc123",
            scope=VoiceScope.USER,
        )
        with self.assertRaises(Exception):
            voice.full_clean()


class VoiceAccessTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Test Org")
        self.user = User.objects.create_user(username="voiceuser", password="test")
        self.other = User.objects.create_user(username="other", password="test")

        self.system_voice = Voice.objects.create(
            name="Coral",
            slug="coral",
            provider=VoiceProvider.OPENAI,
            provider_voice_id="coral",
            scope=VoiceScope.SYSTEM,
        )
        self.user_voice = Voice.objects.create(
            name="My Clone",
            slug="my-clone",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="el-voice-1",
            scope=VoiceScope.USER,
            user=self.user,
        )
        self.other_voice = Voice.objects.create(
            name="Other Clone",
            slug="other-clone",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="el-voice-2",
            scope=VoiceScope.USER,
            user=self.other,
        )

    def test_resolve_accessible_voices_includes_system_and_own(self):
        voices = list(resolve_accessible_voices(user=self.user, organization=self.org))
        ids = {v.id for v in voices}
        self.assertIn(self.system_voice.id, ids)
        self.assertIn(self.user_voice.id, ids)
        self.assertNotIn(self.other_voice.id, ids)

    def test_get_voice_by_id_rejects_inaccessible(self):
        with self.assertRaises(ValueError):
            get_voice_by_id(str(self.other_voice.id), user=self.user, organization=self.org)

    def test_default_system_voice(self):
        voice = get_default_system_voice()
        self.assertEqual(voice.provider_voice_id, DEFAULT_OPENAI_VOICE_ID)


class ListVoicesToolTests(TestCase):
    def setUp(self):
        from api.ai_layers.models import Agent
        from api.messaging.models import Conversation

        self.org = Organization.objects.create(name="Voice List Org")
        self.user = User.objects.create_user(username="voicelistuser", password="test")
        self.other = User.objects.create_user(username="voicelistother", password="test")
        self.default_voice = Voice.objects.create(
            name="Coral",
            slug="coral",
            provider=VoiceProvider.OPENAI,
            provider_voice_id="coral",
            scope=VoiceScope.SYSTEM,
        )
        self.user_voice = Voice.objects.create(
            name="My Voice",
            slug="my-voice",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="my-voice-id",
            scope=VoiceScope.USER,
            user=self.user,
        )
        Voice.objects.create(
            name="Other Voice",
            slug="other-voice",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="other-voice-id",
            scope=VoiceScope.USER,
            user=self.other,
        )
        self.agent = Agent.objects.create(
            name="Voice List Agent",
            slug="voice-list-agent",
            salute="Hi",
            default_voice=self.default_voice,
            organization=self.org,
            user=self.user,
        )
        self.conversation = Conversation.objects.create(
            user=self.user,
            organization=self.org,
        )

    def test_list_voices_returns_only_accessible_voices_and_marks_default(self):
        from api.ai_layers.tools.list_voices import _list_voices_impl

        result = _list_voices_impl(
            conversation_id=str(self.conversation.id),
            user_id=self.user.id,
            agent_slug=self.agent.slug,
        )

        ids = {voice.voice_id for voice in result.voices}
        self.assertEqual(
            ids,
            {str(self.default_voice.id), str(self.user_voice.id)},
        )
        self.assertEqual(result.default_voice_id, str(self.default_voice.id))
        default_item = next(voice for voice in result.voices if voice.is_default)
        self.assertEqual(default_item.voice_id, str(self.default_voice.id))

    def test_list_voices_is_resolved_only_with_create_speech(self):
        from api.ai_layers.tools import resolve_tools

        context = {
            "conversation_id": str(self.conversation.id),
            "user_id": self.user.id,
            "agent_slug": self.agent.slug,
        }
        speech_tool_names = {
            tool["name"] for tool in resolve_tools(["create_speech"], **context)
        }
        standalone_tool_names = {
            tool["name"] for tool in resolve_tools(["list_voices"], **context)
        }

        self.assertEqual(speech_tool_names, {"create_speech", "list_voices"})
        self.assertEqual(standalone_tool_names, set())


class CreateSpeechVoiceResolutionTests(TestCase):
    def setUp(self):
        from api.ai_layers.models import Agent

        self.org = Organization.objects.create(name="Speech Org")
        self.user = User.objects.create_user(username="speechuser", password="test")
        self.system_coral = Voice.objects.create(
            name="Coral",
            slug="coral",
            provider=VoiceProvider.OPENAI,
            provider_voice_id="coral",
            scope=VoiceScope.SYSTEM,
        )
        self.system_marin = Voice.objects.create(
            name="Marin",
            slug="marin",
            provider=VoiceProvider.OPENAI,
            provider_voice_id="marin",
            scope=VoiceScope.SYSTEM,
        )
        self.agent = Agent.objects.create(
            name="Speaker",
            slug="speaker",
            salute="Hi",
            default_voice=self.system_marin,
            user=self.user,
        )

    def test_resolve_explicit_voice_id(self):
        voice = resolve_voice_for_speech(
            voice_id=str(self.system_coral.id),
            agent=self.agent,
            user=self.user,
            organization=self.org,
        )
        self.assertEqual(voice.id, self.system_coral.id)

    def test_resolve_agent_default_when_no_voice_id(self):
        voice = resolve_voice_for_speech(
            voice_id=None,
            agent=self.agent,
            user=self.user,
            organization=self.org,
        )
        self.assertEqual(voice.id, self.system_marin.id)

    def test_resolve_system_default_when_agent_has_no_voice(self):
        self.agent.default_voice = None
        self.agent.save(update_fields=["default_voice"])
        voice = resolve_voice_for_speech(
            voice_id=None,
            agent=self.agent,
            user=self.user,
            organization=self.org,
        )
        self.assertEqual(voice.provider_voice_id, DEFAULT_OPENAI_VOICE_ID)

    @patch("api.voices.synthesis.synthesize_speech_bytes", return_value=(b"audio", "gpt-4o-mini-tts"))
    def test_create_speech_uses_voice_catalog(self, _mock):
        from api.ai_layers.models import Agent
        from api.ai_layers.tools.create_speech import _create_speech_impl
        from api.messaging.models import Conversation

        conv = Conversation.objects.create(user=self.user, organization=self.org)
        agent = Agent.objects.get(slug="speaker")

        with patch(
            "api.ai_layers.tools.embedded_channels.conversation_uses_capability_gated_media_tools",
            return_value=False,
        ), patch(
            "api.authenticate.services.FeatureFlagService.is_feature_enabled",
            return_value=(True, "on"),
        ):
            result = _create_speech_impl(
                text="Hello world",
                voice_id=str(self.system_coral.id),
                instructions="",
                output_format="mp3",
                conversation_id=str(conv.id),
                user_id=self.user.id,
                agent_slug=agent.slug,
            )

        self.assertEqual(result.voice_id, str(self.system_coral.id))
        self.assertEqual(result.voice_name, "Coral")

    @patch("api.voices.synthesis._generate_elevenlabs_tts_bytes", return_value=b"el-audio")
    def test_synthesize_elevenlabs_voice(self, _mock):
        from api.voices.synthesis import synthesize_speech_bytes

        voice = Voice.objects.create(
            name="Clone",
            slug="clone",
            provider=VoiceProvider.ELEVENLABS,
            provider_voice_id="el-123",
            scope=VoiceScope.USER,
            user=self.user,
            metadata={"model_id": "eleven_multilingual_v2"},
        )
        audio, model = synthesize_speech_bytes(voice=voice, text="test")
        self.assertEqual(audio, b"el-audio")
        self.assertEqual(model, "eleven_multilingual_v2")


class VoicePreviewTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Preview Org")
        self.user = User.objects.create_user(username="previewuser", password="test")

        self.system_voice = Voice.objects.create(
            name="Coral",
            slug="coral",
            provider=VoiceProvider.OPENAI,
            provider_voice_id="coral",
            scope=VoiceScope.SYSTEM,
        )

    @patch("api.voices.preview.synthesize_speech_bytes", return_value=(b"preview-mp3", "gpt-4o-mini-tts"))
    def test_get_or_create_voice_preview_url_caches_file(self, _mock):
        from django.test import override_settings

        from api.voices.preview import get_or_create_voice_preview_url

        with override_settings(MEDIA_ROOT="/tmp/masscer-test-media"):
            url1 = get_or_create_voice_preview_url(voice=self.system_voice)
            url2 = get_or_create_voice_preview_url(voice=self.system_voice)
        self.assertIn("voice_previews", url1)
        self.assertEqual(url1, url2)
        _mock.assert_called_once()

    @patch("api.voices.views.get_or_create_voice_preview_url", return_value="/media/voice_previews/x.mp3")
    def test_voice_preview_endpoint(self, _mock):
        from django.test import Client

        from api.authenticate.models import Token

        token = Token.objects.create(user=self.user, token_type="permanent")
        client = Client()
        response = client.post(
            "/v1/voices/preview/",
            data='{"voice_id": "%s"}' % self.system_voice.id,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["voice_id"], str(self.system_voice.id))
        self.assertIn("url", body)


class SyncSystemVoicesTests(TestCase):
    def test_sync_creates_openai_and_elevenlabs_system_voices(self):
        from api.voices.constants import SYSTEM_ELEVENLABS_VOICES, SYSTEM_OPENAI_VOICES
        from api.voices.seed import sync_system_voices

        created, updated, unchanged = sync_system_voices()
        self.assertGreater(len(created), 0)

        from api.voices.models import Voice, VoiceProvider, VoiceScope

        self.assertEqual(
            Voice.objects.filter(scope=VoiceScope.SYSTEM, provider=VoiceProvider.OPENAI).count(),
            len(SYSTEM_OPENAI_VOICES),
        )
        self.assertEqual(
            Voice.objects.filter(
                scope=VoiceScope.SYSTEM,
                provider=VoiceProvider.ELEVENLABS,
                is_active=True,
            ).count(),
            len(SYSTEM_ELEVENLABS_VOICES),
        )

        created2, updated2, unchanged2 = sync_system_voices()
        self.assertEqual(created2, [])
        self.assertEqual(updated2, [])
        self.assertEqual(len(unchanged2), len(SYSTEM_OPENAI_VOICES) + len(SYSTEM_ELEVENLABS_VOICES))
