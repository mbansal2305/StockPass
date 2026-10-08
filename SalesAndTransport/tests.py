import base64
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase
from PIL import Image, ImageDraw

from SalesAndTransport.api.master import (
    prepare_profile_picture,
    save_profile_picture,
    select_all_clients,
    select_firms,
    validate_content,
)
from SalesAndTransport.api.bills import (
    BillTransportLookupSchema,
    get_transport_by_bill,
)
from SalesAndTransport.api.transport import (
    serialize_billing_firm_image,
    serialize_transport,
    serialize_transporter_bank,
    update_transport_status,
)
from SalesAndTransport.api.order import serialize_order
from SalesAndTransport.schemas.order import OrderOutSchema
from SalesAndTransport.schemas.transport import (
    TransportPaymentsListSchema,
    TransportStatusUpdateSchema,
    TransportOutSchema,
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


class BillTransportLookupTests(TestCase):
    @patch("SalesAndTransport.api.bills.Transport.objects")
    def test_returns_details_for_first_matching_transport(self, objects):
        transport = SimpleNamespace(
            from_client=SimpleNamespace(name="Origin"),
            to_client=SimpleNamespace(name="Destination"),
            vehicle_no="ABC-123",
            gross_wt=Decimal("12.500"),
            quantity_unit="quintal",
            rent=Decimal("1500.00"),
            rent_type="per_unit",
        )
        (
            objects.filter.return_value.select_related.return_value
            .order_by.return_value.first.return_value
        ) = transport

        result = get_transport_by_bill(
            request=None,
            data=BillTransportLookupSchema(billing_firm_id=2, bill_no="B-1"),
        )

        objects.filter.assert_called_once_with(
            is_active=True,
            billing_firm_id=2,
            bill_no="B-1",
        )
        objects.filter.return_value.select_related.assert_called_once_with(
            "from_client",
            "to_client",
        )
        objects.filter.return_value.select_related.return_value.order_by.assert_called_once_with(
            "id",
        )
        self.assertEqual(
            result,
            {
                "from_client": "Origin",
                "to_client": "Destination",
                "vehicle_no": "ABC-123",
                "gross_wt": Decimal("12.500"),
                "gross_wt_unit": "quintal",
                "rent": Decimal("1500.00"),
                "rent_type": "per_unit",
            },
        )


class SelectFirmsTests(TestCase):
    @patch("SalesAndTransport.api.master.BusinessClient.objects")
    @patch("SalesAndTransport.api.master.default_storage")
    def test_only_returns_picture_url_when_file_exists(self, storage, objects):
        firms = [
            SimpleNamespace(
                id=1,
                name="Firm with picture",
                active_profile_pictures=[
                    SimpleNamespace(
                        url="https://example.com/media/profile_picture/firm.jpg",
                    ),
                ],
            ),
            SimpleNamespace(
                id=2,
                name="Firm with missing picture file",
                active_profile_pictures=[
                    SimpleNamespace(
                        url="https://example.com/media/profile_picture/missing.jpg",
                    ),
                ],
            ),
            SimpleNamespace(
                id=3,
                name="Firm without picture record",
                active_profile_pictures=[],
            ),
        ]
        (
            objects.filter.return_value.prefetch_related.return_value.order_by.return_value
        ) = firms
        storage.exists.side_effect = [True, False]

        result = select_firms(request=None)

        objects.filter.assert_called_once_with(
            is_active=True,
            type="my_firm",
        )
        self.assertEqual(
            result["data"],
            [
                {
                    "id": 1,
                    "name": "Firm with picture",
                    "profile_picture": (
                        "https://example.com/media/profile_picture/firm.jpg"
                    ),
                },
                {
                    "id": 2,
                    "name": "Firm with missing picture file",
                    "profile_picture": None,
                },
                {
                    "id": 3,
                    "name": "Firm without picture record",
                    "profile_picture": None,
                },
            ],
        )
        self.assertEqual(
            [call.args[0] for call in storage.exists.call_args_list],
            [
                "profile_picture/firm.jpg",
                "profile_picture/missing.jpg",
            ],
        )


class SelectAllClientsTests(TestCase):
    @patch("SalesAndTransport.api.master.BusinessClient.objects")
    def test_returns_requested_fields_for_active_clients_of_all_types(self, objects):
        clients = [
            {
                "id": 1,
                "name": "Company Client",
                "type": "company",
                "maan_no": "12345",
                "city": "Mumbai",
            },
            {
                "id": 2,
                "name": "Godown Client",
                "type": "other_godown",
                "maan_no": None,
                "city": None,
            },
        ]
        objects.filter.return_value.order_by.return_value.values.return_value = clients

        result = select_all_clients(request=None)

        objects.filter.assert_called_once_with(is_active=True)
        objects.filter.return_value.order_by.return_value.values.assert_called_once_with(
            "id",
            "name",
            "type",
            "maan_no",
            "city",
        )
        self.assertEqual(result["data"], clients)


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


class TransportStatusUpdateTests(TestCase):
    def test_schema_accepts_only_allowed_statuses(self):
        for status in ("pending", "delivery", "finance", "paid", "draft"):
            with self.subTest(status=status):
                data = TransportStatusUpdateSchema(id=12, status=status)
                self.assertEqual(data.status, status)

        with self.assertRaises(ValueError):
            TransportStatusUpdateSchema(id=12, status="completed")

    @patch("SalesAndTransport.api.transport.get_object_or_404")
    def test_updates_status_and_modification_metadata(self, get_transport):
        user = object()
        transport = SimpleNamespace(id=12, status="pending", save=Mock())
        get_transport.return_value = transport
        request = SimpleNamespace(auth=user)

        response = update_transport_status(
            request,
            TransportStatusUpdateSchema(id=12, status="paid"),
        )

        get_transport.assert_called_once()
        self.assertEqual(transport.status, "paid")
        self.assertIs(transport.m_by, user)
        transport.save.assert_called_once_with(
            update_fields=["status", "m_by", "m_at"],
        )
        self.assertEqual(
            response["data"],
            {"id": 12, "status": "paid"},
        )


class SerializeTransportForeignKeyTests(TestCase):
    def test_serializes_foreign_key_ids(self):
        transport = SimpleNamespace(
            id=1,
            billing_firm=SimpleNamespace(name="Firm"),
            billing_firm_id=2,
            bill_no="B-1",
            bulk_transport=None,
            commodity=SimpleNamespace(name="Wheat", type=None),
            commodity_id=3,
            loading_date=None,
            from_client=SimpleNamespace(name="From client"),
            from_client_id=4,
            to_client=SimpleNamespace(name="To client"),
            to_client_id=5,
            gross_wt=0,
            quantity_unit="quintal",
            bag_nos=0,
            bag_wt=0,
            vehicle_no=None,
            transporter=SimpleNamespace(name="Transporter"),
            transporter_id=6,
            anugya=False,
            gatepass=False,
            unload_date=None,
            rcvd_wt=0,
            rent_type="per_unit",
            rent=0,
            adv_by_client=0,
            adv_by_firm=0,
            final_paid=0,
            extra_paid=0,
            shortage=0,
            status="pending",
            notes=None,
            wt_rcpt_src=None,
            wt_rcpt_dst=None,
            items=SimpleNamespace(all=lambda: []),
        )

        data = serialize_transport(transport)
        response = TransportOutSchema(**data)

        self.assertEqual(
            {
                field: getattr(response, field)
                for field in (
                    "billing_firm_id",
                    "commodity_id",
                    "from_client_id",
                    "to_client_id",
                    "transporter_id",
                )
            },
            {
                "billing_firm_id": 2,
                "commodity_id": 3,
                "from_client_id": 4,
                "to_client_id": 5,
                "transporter_id": 6,
            },
        )


class SerializeOrderForeignKeyTests(TestCase):
    def test_serializes_foreign_key_ids_in_response_schema(self):
        order = SimpleNamespace(
            id=1,
            type="sales_order",
            order_no="SO-1",
            from_client=SimpleNamespace(name="From client"),
            from_client_id=2,
            to_client=SimpleNamespace(name="To client"),
            to_client_id=3,
            commodity=SimpleNamespace(name="Wheat", type="grain"),
            commodity_id=4,
            rate=Decimal("12.50"),
            quantity=Decimal("10"),
            quantity_unit="quintal",
            start_date=None,
            expiry_date=None,
            contract_date=None,
            quantity_fulfilled=Decimal("0"),
            broker=SimpleNamespace(name="Broker"),
            broker_id=5,
            status="pending",
            notes=None,
            is_active=True,
        )

        response = OrderOutSchema(**serialize_order(order))

        self.assertEqual(
            (
                response.from_client_id,
                response.to_client_id,
                response.broker_id,
                response.commodity_id,
            ),
            (2, 3, 5, 4),
        )


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
