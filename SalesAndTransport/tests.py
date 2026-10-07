import base64
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from SalesAndTransport.api.transport import serialize_billing_firm_image


class SerializeBillingFirmImageTests(TestCase):
    def test_returns_base64_and_url_when_picture_exists_in_media(self):
        picture_url = "https://example.com/media/profile_picture/image.jfif"
        billing_firm = SimpleNamespace(
            active_profile_pictures=[SimpleNamespace(url=picture_url)],
        )
        image_content = b"profile picture"

        with patch(
            "SalesAndTransport.api.transport.default_storage",
        ) as storage:
            storage.open.return_value.__enter__.return_value.read.return_value = (
                image_content
            )

            image, image_url = serialize_billing_firm_image(billing_firm)

        self.assertEqual(image, base64.b64encode(image_content).decode("ascii"))
        self.assertEqual(image_url, picture_url)

    def test_returns_none_when_profile_picture_file_is_missing(self):
        billing_firm = SimpleNamespace(
            active_profile_pictures=[
                SimpleNamespace(
                    url="https://example.com/media/profile_picture/missing.jfif",
                )
            ],
        )

        with patch(
            "SalesAndTransport.api.transport.default_storage",
        ) as storage:
            storage.open.side_effect = FileNotFoundError

            image, image_url = serialize_billing_firm_image(billing_firm)

        self.assertIsNone(image)
        self.assertIsNone(image_url)
