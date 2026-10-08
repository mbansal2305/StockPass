import base64
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase
from PIL import Image, ImageDraw

from SalesAndTransport.api.master import (
    prepare_profile_picture,
    save_profile_picture,
    validate_content,
)
from SalesAndTransport.api.transport import (
    serialize_billing_firm_image,
    serialize_transporter_bank,
)
from SalesAndTransport.schemas.transport import (
    TransportPaymentsListSchema,
    TransporterBankSchema,
)


class TransporterMasterContentTests(TestCase):
    def test_accepts_bank_details_for_add_and_update_content(self):
        validate_content(
            "transporter",
            {
                "transaction_type": "NEFT",
                "account_number": "12345678901234567890",
                "account_name": "Transporter Account",
                "ifsc_code": "BANK012345678901234",
                "bank": "Example Bank",
                "branch": "Main Branch",
                "email": "transporter@example.com",
            },
        )


class BusinessClientMasterContentTests(TestCase):
    def test_accepts_maan_no_for_add_and_update_content(self):
        validate_content("businessclient", {"maan_no": "1234567890"})


class PrepareProfilePictureTests(TestCase):
    def test_resizes_and_center_crops_landscape_image(self):
        image = Image.new("RGB", (400, 200), (0, 128, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 99, 199), fill=(255, 0, 0))
        draw.rectangle((300, 0, 399, 199), fill=(0, 0, 255))

        source = BytesIO()
        image.save(source, format="PNG")
        image_data, extension = prepare_profile_picture(
            base64.b64encode(source.getvalue()).decode("ascii")
        )

        with Image.open(BytesIO(image_data)) as result:
            self.assertEqual(result.size, (256, 256))
            self.assertEqual(result.getpixel((10, 128)), (0, 128, 0))
            self.assertEqual(result.getpixel((245, 128)), (0, 128, 0))
        self.assertEqual(extension, "png")

    def test_upscales_square_image_to_256_pixels(self):
        source = BytesIO()
        Image.new("RGB", (64, 64), (12, 34, 56)).save(source, format="PNG")

        image_data, _ = prepare_profile_picture(
            base64.b64encode(source.getvalue()).decode("ascii")
        )

        with Image.open(BytesIO(image_data)) as result:
            self.assertEqual(result.size, (256, 256))
            self.assertEqual(result.getpixel((128, 128)), (12, 34, 56))


class SaveProfilePictureTests(TestCase):
    def test_replacement_deletes_previous_media_file(self):
        picture = SimpleNamespace(
            pk=1,
            url="https://example.com/media/profile_picture/old.jpg",
            save=Mock(),
        )
        pictures = Mock()
        pictures.order_by.return_value.first.return_value = picture
        business_client = SimpleNamespace(profile_pictures=Mock())
        business_client.profile_pictures.filter.return_value = pictures
        request = SimpleNamespace(
            auth=None,
            build_absolute_uri=lambda url: f"https://example.com{url}",
        )

        with (
            patch("SalesAndTransport.api.master.default_storage") as storage,
            patch(
                "SalesAndTransport.api.master.transaction.on_commit",
                side_effect=lambda callback: callback(),
            ),
        ):
            storage.save.return_value = "profile_picture/new.png"
            storage.url.return_value = "/media/profile_picture/new.png"

            save_profile_picture(request, business_client, (b"image", "png"))

        storage.delete.assert_called_once_with("profile_picture/old.jpg")
        self.assertEqual(
            picture.url,
            "https://example.com/media/profile_picture/new.png",
        )


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


class TransportPaymentsListSchemaTests(TestCase):
    def test_has_its_own_filters_and_pagination_defaults(self):
        data = TransportPaymentsListSchema(transporter=12, status="paid")

        self.assertEqual(data.transporter, 12)
        self.assertEqual(data.status, "paid")
        self.assertEqual(data.page, 1)
        self.assertEqual(data.page_size, 100)


class SerializeTransporterBankTests(TestCase):
    def test_serializes_all_transporter_bank_fields(self):
        transporter = SimpleNamespace(
            transaction_type="NEFT",
            account_number="12345678901234567890",
            account_name="Transporter Account",
            ifsc_code="BANK012345678901234",
            bank="Example Bank",
            branch="Main Branch",
            email="transporter@example.com",
        )

        bank_details = serialize_transporter_bank(transporter)

        self.assertEqual(
            bank_details,
            {
                "transaction_type": "NEFT",
                "account_number": "12345678901234567890",
                "account_name": "Transporter Account",
                "ifsc_code": "BANK012345678901234",
                "bank": "Example Bank",
                "branch": "Main Branch",
                "email": "transporter@example.com",
            },
        )
        validated_details = TransporterBankSchema(**bank_details).model_dump()
        self.assertEqual(validated_details, bank_details)

    def test_returns_all_keys_when_transport_has_no_transporter(self):
        bank_details = serialize_transporter_bank(None)

        self.assertEqual(
            bank_details,
            {
                "transaction_type": None,
                "account_number": None,
                "account_name": None,
                "ifsc_code": None,
                "bank": None,
                "branch": None,
                "email": None,
            },
        )
