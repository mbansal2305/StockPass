from datetime import date
from decimal import Decimal
from typing import Literal

from ninja import Schema


TimeRange = Literal["all_time", "this_month", "this_week"]


class DashboardRequestSchema(Schema):
    time_range: TimeRange = "all_time"


class DashboardOrderSchema(Schema):
    id: int
    order_no: str | None
    type: str
    expiry_date: date
    days_until_expiry: int
    quantity: Decimal
    quantity_unit: str
    quantity_fulfilled: Decimal
    from_client: str | None
    to_client: str | None
    commodity: str


class DashboardTransportSchema(Schema):
    id: int
    vehicle_no: str | None
    bill_no: str | None
    status: str
    gross_wt: Decimal
    quantity_unit: str
    unload_date: date | None


class DashboardDataSchema(Schema):
    time_range: TimeRange
    pending_orders_count: int
    draft_orders_count: int
    expiring_orders: list[DashboardOrderSchema]
    in_transit_count: int
    transport_status_counts: dict[str, int]
    in_transit_transports: list[DashboardTransportSchema]


class DashboardResponseSchema(Schema):
    success: bool
    data: DashboardDataSchema