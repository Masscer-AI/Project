from django.test import SimpleTestCase


class ImageModelPricingTests(SimpleTestCase):
    def test_gpt_image_2_has_conservative_flat_price(self):
        from api.consumption.actions import (
            IMAGE_MODEL_PRICING_USD,
            calculate_consumption_image_generation,
        )

        self.assertEqual(IMAGE_MODEL_PRICING_USD["gpt-image-2"], 0.053)
        self.assertEqual(calculate_consumption_image_generation("gpt-image-2"), 0.053)

    def test_unsupported_image_model_pricing_raises(self):
        from api.consumption.actions import calculate_consumption_image_generation

        with self.assertRaises(ValueError):
            calculate_consumption_image_generation("not-a-real-image-model")
