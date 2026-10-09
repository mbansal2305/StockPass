import json
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from ninja import Schema
from pydantic import field_validator


TransportStatus = Literal[
    "pending",
    "delivery",
    "finance",
    "paid",
    "draft",
]
QuantityUnit = Literal["mt", "quintal", "kg"]
RentType = Literal["fix", "per_unit"]


def parse_items_form_value(value):
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
        value = value[0]
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as error:
            raise ValueError("items must be a JSON-encoded list") from error
    return value


class TransportItemInputSchema(Schema):
    id: Optional[int] = None
    order: int
    quantity: Optional[Decimal] = None
    order_entry: Optional[Decimal] = None


class TransportCreateSchema(Schema):
    billing_firm: int
    bill_no: Optional[str] = None
    commodity: int
    from_client: Optional[int] = None
    to_client: Optional[int] = None
    gross_wt: Decimal = Decimal("0")
    gross_wt_unit: QuantityUnit = "quintal"
    bag_nos: Decimal = Decimal("0")
    bag_wt: Decimal = Decimal("0")
    vehicle_no: Optional[str] = None
    transporter: Optional[int] = None
    anugya: bool = False
    gatepass: bool = False
    loading_date: Optional[date] = None
    unload_date: Optional[date] = None
    rcvd_wt: Decimal = Decimal("0")
    rent_type: Optional[RentType] = None
    rent: Decimal = Decimal("0")
    adv_by_client: Decimal = Decimal("0")
    adv_by_firm: Decimal = Decimal("0")
    final_paid: Decimal = Decimal("0")
    extra_paid: Decimal = Decimal("0")
    shortage : Optional[Decimal] = Decimal("0")
    status: TransportStatus = "pending"
    notes: Optional[str] = None
    items: list[TransportItemInputSchema]

    @field_validator("items", mode="before")
    @classmethod
    def parse_items_form_value(cls, value):
        return parse_items_form_value(value)


class TransportUpdateSchema(Schema):
    id: int
    billing_firm: Optional[int] = None
    bill_no: Optional[str] = None
    commodity: Optional[int] = None
    from_client: Optional[int] = None
    to_client: Optional[int] = None
    gross_wt: Optional[Decimal] = None
    gross_wt_unit: Optional[QuantityUnit] = None
    bag_nos: Optional[Decimal] = None
    bag_wt: Optional[Decimal] = None
    vehicle_no: Optional[str] = None
    transporter: Optional[int] = None
    anugya: Optional[bool] = None
    gatepass: Optional[bool] = None
    loading_date: Optional[date] = None
    unload_date: Optional[date] = None
    rcvd_wt: Optional[Decimal] = None
    rent_type: Optional[RentType] = None
    rent: Optional[Decimal] = None
    adv_by_client: Optional[Decimal] = None
    adv_by_firm: Optional[Decimal] = None
    final_paid: Optional[Decimal] = None
    extra_paid: Optional[Decimal] = None
    shortage : Optional[Decimal] = None
    status: Optional[TransportStatus] = None
    notes: Optional[str] = None
    items: Optional[list[TransportItemInputSchema]] = None

    @field_validator("items", mode="before")
    @classmethod
    def parse_items_form_value(cls, value):
        return parse_items_form_value(value)


class TransportGetDeleteSchema(Schema):
    id: int


class TransportStatusUpdateSchema(Schema):
    id: int
    status: TransportStatus


class TransportListSchema(Schema):
    transporter: Optional[list[int]] = None
    status: Optional[TransportStatus] = None
    commodity: Optional[list[int]] = None
    billing_firm: Optional[list[int]] = None
    party: Optional[list[int]] = None
    loading_start_date: Optional[date] = None
    loading_end_date: Optional[date] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = 100


class TransportPaymentsListSchema(Schema):
    transporter: Optional[list[int]] = None
    status: Optional[TransportStatus] = None
    commodity: Optional[list[int]] = None
    billing_firm: Optional[list[int]] = None
    party: Optional[list[int]] = None
    loading_start_date: Optional[date] = None
    loading_end_date: Optional[date] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = 100


class TransportSearchSchema(Schema):
    keyword: str


class TransportItemOutSchema(Schema):
    id: int
    order_id: Optional[int]
    order: Optional[str]
    order_type: Optional[str] = None
    order_size: Optional[Decimal] = None
    order_size_rem: Optional[Decimal] = None
    order_size_unit: Optional[str] = None
    order_commodity: Optional[str] = None
    order_commodity_type: Optional[str] = None
    quantity: Decimal
    order_entry: Decimal


class TransportOutSchema(Schema):
    id: int
    billing_firm: str
    billing_firm_id: int
    bill_no: Optional[str]
    bulk_transport: Optional[str]
    commodity: str
    commodity_id: Optional[int]
    commodity_type : Optional[str]
    loading_date: Optional[date]
    from_client: Optional[str]
    from_client_id: Optional[int]
    to_client: Optional[str]
    to_client_id: Optional[int]
    gross_wt: Decimal
    gross_wt_unit: str
    bag_nos: Decimal
    bag_wt: Decimal
    vehicle_no: Optional[str]
    transporter: Optional[str]
    transporter_id: Optional[int]
    anugya: bool
    gatepass: bool
    unload_date: Optional[date]
    rcvd_wt: Decimal
    rent_type: str
    rent: Decimal
    adv_by_client: Decimal
    adv_by_firm: Decimal
    final_paid: Decimal
    extra_paid: Decimal
    shortage : Decimal = None
    status: str
    notes: Optional[str]
    wt_rcpt_src: Optional[str]
    wt_rcpt_dst: Optional[str]
    items: list[TransportItemOutSchema]


class TransportListOutSchema(TransportOutSchema):
    image: Optional[str] = None
    image_url: Optional[str] = None


class TransporterBankSchema(Schema):
    transaction_type: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    bank: Optional[str] = None
    branch: Optional[str] = None
    email: Optional[str] = None


class TransportPaymentsListOutSchema(TransportListOutSchema):
    transporter_bank: TransporterBankSchema


class TransportDetailResponseSchema(Schema):
    success: bool
    data: TransportOutSchema


class TransportPageSchema(Schema):
    page: int
    page_size: int
    total: int
    total_pages: int
    results: list[TransportListOutSchema]


class TransportListResponseSchema(Schema):
    success: bool
    data: TransportPageSchema


class TransportPaymentsPageSchema(Schema):
    page: int
    page_size: int
    total: int
    total_pages: int
    results: list[TransportPaymentsListOutSchema]


class TransportPaymentsListResponseSchema(Schema):
    success: bool
    data: TransportPaymentsPageSchema


class TransportSearchResponseSchema(Schema):
    success: bool
    total: int
    results: list[TransportOutSchema]


class TransportDeleteResponseSchema(Schema):
    success: bool
    id: int