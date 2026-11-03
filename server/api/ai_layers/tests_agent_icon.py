from django.test import SimpleTestCase

from api.ai_layers.models import AgentIcon
from api.ai_layers.serializers import AgentSerializer


class AgentIconSerializerTests(SimpleTestCase):
    def test_known_icon_is_accepted(self):
        serializer = AgentSerializer(data={"icon": AgentIcon.SCALE}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["icon"], AgentIcon.SCALE)

    def test_unknown_icon_is_rejected(self):
        serializer = AgentSerializer(data={"icon": "<svg>"}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn("icon", serializer.errors)
