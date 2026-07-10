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
