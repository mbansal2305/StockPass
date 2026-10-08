import json
from datetime import date
from decimal import Decimal
from typing import Optional

from ninja import Schema
from pydantic import field_validator

from SalesAndTransport.schemas.transport import (
    TransportCreateSchema,
    TransportOutSchema,
    TransportStatus,
)


class BulkTransportChildSchema(TransportCreateSchema):
    id: Optional[int] = None
    billing_firm: Optional[int] = None
    commodity: Optional[int] = None


class BulkTransportCreateSchema(Schema):
    title: str
    loading_date: Optional[date] = None
    total_rcvd_wt: Optional[Decimal] = None
    bill_no: Optional[str] = None
    order: Optional[int] = None
    billing_firm: Optional[int] = None
    transporter: Optional[int] = None
    to_client: Optional[int] = None
    commodity: Optional[int] = None
    status: TransportStatus = "pending"
    transports: list[BulkTransportChildSchema]

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        if not value.strip():
            raise ValueError("title is required")
        return value.strip()

    @field_validator("transports", mode="before")
    @classmethod
    def parse_transports_form_value(cls, value):
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
            value = value[0]
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as error:
                raise ValueError("transports must be a JSON-encoded list") from error
        return value


class BulkTransportUpdateSchema(Schema):
    id: int
    title: Optional[str] = None
    loading_date: Optional[date] = None
    total_rcvd_wt: Optional[Decimal] = None
    bill_no: Optional[str] = None
    order: Optional[int] = None
    billing_firm: Optional[int] = None
    transporter: Optional[int] = None
    to_client: Optional[int] = None
    commodity: Optional[int] = None
    status: Optional[TransportStatus] = None
    transports: list[BulkTransportChildSchema]

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        if value is not None and not value.strip():
            raise ValueError("title cannot be empty")
        return value.strip() if value is not None else None

    @field_validator("transports", mode="before")
    @classmethod
    def parse_transports_form_value(cls, value):
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
            value = value[0]
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as error:
                raise ValueError("transports must be a JSON-encoded list") from error
        return value


class BulkTransportGetDeleteSchema(Schema):
    id: int


class BulkTransportListSchema(Schema):
    page: int = 1
    page_size: int = 10


class BulkTransportSearchSchema(Schema):
    title: str


class BulkTransportOutSchema(Schema):
    id: int
    title: str
    loading_date: Optional[date]
    total_rcvd_wt: Decimal
    bill_no: Optional[str]
    order: Optional[int]
    billing_firm: Optional[int]
    transporter: Optional[int]
    to_client: Optional[int]
    commodity: Optional[int]
    status: str
    selected_sources: list[int]
    transports: list[TransportOutSchema]


class BulkTransportDetailResponseSchema(Schema):
    success: bool
    data: BulkTransportOutSchema


class BulkTransportListItemSchema(Schema):
    id: int
    loading_date: Optional[date]
    title: str
    commodity: Optional[str]
    bill_no: Optional[str]
    order: Optional[str]
    billing_firm: Optional[str]
    to_client: Optional[str]
    status: str
    num_vehicles: int


class BulkTransportPageSchema(Schema):
    page: int
    page_size: int
    total: int
    total_pages: int
    results: list[BulkTransportListItemSchema]


class BulkTransportListResponseSchema(Schema):
    success: bool
    data: BulkTransportPageSchema


class BulkTransportSearchResponseSchema(Schema):
    success: bool
    total: int
    results: list[BulkTransportOutSchema]


class BulkTransportDeleteResponseSchema(Schema):
    success: bool
    id: int