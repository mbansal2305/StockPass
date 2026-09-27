import json
from typing import Optional

from ninja import Schema
from pydantic import field_validator

from SalesAndTransport.schemas.transport import (
    TransportOutSchema,
    TransportCreateSchema,
    TransportUpdateSchema,
)


class BulkTransportCreateSchema(Schema):
    title: str
    transports: list[TransportCreateSchema]

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        if not value.strip():
            raise ValueError("title is required")
        return value.strip()

    @field_validator("transports", mode="before")
    @classmethod
    def parse_transports_form_value(cls, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as error:
                raise ValueError("transports must be a JSON-encoded list") from error
        return value


class BulkTransportUpdateSchema(Schema):
    id: int
    title: Optional[str] = None
    transports: Optional[list[TransportUpdateSchema]] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        if value is not None and not value.strip():
            raise ValueError("title cannot be empty")
        return value.strip() if value is not None else None

    @field_validator("transports", mode="before")
    @classmethod
    def parse_transports_form_value(cls, value):
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
    transports: list[TransportOutSchema]


class BulkTransportDetailResponseSchema(Schema):
    success: bool
    data: BulkTransportOutSchema


class BulkTransportPageSchema(Schema):
    page: int
    page_size: int
    total: int
    total_pages: int
    results: list[BulkTransportOutSchema]


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