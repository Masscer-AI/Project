from django.contrib.auth.models import User
from django.test import TestCase
from pydantic import ValidationError

from api.authenticate.models import UserProfile
from api.authenticate.phone_numbers import (
    PhoneNumber,
    PhoneNumbers,
    default_phone_numbers_list,
    parse_phone_numbers,
    validate_phone_numbers_for_storage,
)
from api.authenticate.serializers import UserProfileSerializer


class PhoneNumbersSchemaTests(TestCase):
    def test_defaults_empty(self):
        self.assertEqual(default_phone_numbers_list(), [])
        self.assertEqual(parse_phone_numbers(None).root, [])

    def test_normalizes_and_promotes_default(self):
        data = validate_phone_numbers_for_storage(
            [
                {"country_code": "+52", "number": "55 1234 5678", "is_default": False},
            ]
        )
        self.assertEqual(data[0]["country_code"], "52")
        self.assertEqual(data[0]["number"], "5512345678")
        self.assertTrue(data[0]["is_default"])

    def test_rejects_duplicate_e164(self):
        with self.assertRaises(ValidationError):
            PhoneNumbers.model_validate(
                [
                    {
                        "country_code": "52",
                        "number": "5512345678",
                        "is_default": True,
                    },
                    {
                        "country_code": "+52",
                        "number": "55-1234-5678",
                        "is_default": False,
                    },
                ]
            )

    def test_rejects_multiple_defaults(self):
        with self.assertRaises(ValidationError):
            PhoneNumbers.model_validate(
                [
                    {
                        "country_code": "1",
                        "number": "5551112222",
                        "is_default": True,
                    },
                    {
                        "country_code": "1",
                        "number": "5553334444",
                        "is_default": True,
                    },
                ]
            )

    def test_rejects_e164_too_long(self):
        with self.assertRaises(ValidationError):
            PhoneNumber.model_validate(
                {
                    "country_code": "123",
                    "number": "4567890123456",
                    "is_default": True,
                }
            )

    def test_e164_digits(self):
        pn = PhoneNumber.model_validate(
            {"country_code": "52", "number": "5512345678", "is_default": True}
        )
        self.assertEqual(pn.e164_digits(), "525512345678")


class UserProfilePhoneNumbersTests(TestCase):
    def setUp(self):
        from api.ai_layers.models import LanguageModel
        from api.consumption.models import Currency
        from api.providers.models import AIProvider

        Currency.objects.get_or_create(
            name="Compute Unit", defaults={"one_usd_is": 1000}
        )
        provider = AIProvider.objects.create(name="OpenAI-phone-tests")
        LanguageModel.objects.create(
            provider=provider, slug="gpt-phone-tests", name="GPT Phone"
        )
        self.user = User.objects.create_user(username="phoneuser", password="x")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_property_roundtrip(self):
        self.profile.phone_numbers = [
            {"country_code": "1", "number": "5551234567", "is_default": True}
        ]
        self.profile.save()
        self.profile.refresh_from_db()
        parsed = self.profile.phone_numbers
        self.assertEqual(len(parsed.root), 1)
        self.assertEqual(parsed.root[0].e164_digits(), "15551234567")

    def test_serializer_read_write(self):
        serializer = UserProfileSerializer(
            self.profile,
            data={
                "phone_numbers": [
                    {
                        "country_code": "52",
                        "number": "5511112222",
                        "is_default": True,
                    }
                ]
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.profile.refresh_from_db()
        data = UserProfileSerializer(self.profile).data
        self.assertEqual(data["phone_numbers"][0]["number"], "5511112222")

    def test_serializer_rejects_invalid(self):
        serializer = UserProfileSerializer(
            self.profile,
            data={
                "phone_numbers": [
                    {"country_code": "1", "number": "12", "is_default": True}
                ]
            },
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("phone_numbers", serializer.errors)

    def test_serializer_empty_list_clears_phone_numbers(self):
        self.profile.phone_numbers = [
            {"country_code": "593", "number": "0964105554", "is_default": True}
        ]
        self.profile.save()

        serializer = UserProfileSerializer(
            self.profile,
            data={"phone_numbers": []},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile._phone_numbers, [])
        self.assertEqual(UserProfileSerializer(self.profile).data["phone_numbers"], [])
