from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from ninja import Schema


OrderType = Literal["sales_order", "purchase_order"]
OrderStatus = Literal["pending", "completed", "draft"]
QuantityUnit = Literal["mt", "quintal", "kg"]


class OrderCreateSchema(Schema):
    type: OrderType
    order_no: Optional[str] = None
    from_client: Optional[int] = None
    to_client: Optional[int] = None
    commodity: int
    rate: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    quantity_unit: QuantityUnit = "quintal"
    start_date: Optional[date] = None
    expiry_date: Optional[date] = None
    contract_date: Optional[date] = None
    quantity_fulfilled: Decimal = Decimal("0")
    broker: Optional[int] = None
    status: OrderStatus = "draft"
    notes: Optional[str] = None


class OrderUpdateSchema(Schema):
    id: int
    type: Optional[OrderType] = None
    order_no: Optional[str] = None
    from_client: Optional[int] = None
    to_client: Optional[int] = None
    commodity: Optional[int] = None
    rate: Optional[Decimal] = None
    quantity: Optional[Decimal] = None
    quantity_unit: Optional[QuantityUnit] = None
    start_date: Optional[date] = None
    expiry_date: Optional[date] = None
    contract_date: Optional[date] = None
    quantity_fulfilled: Optional[Decimal] = None
    broker: Optional[int] = None
    status: Optional[OrderStatus] = None
    notes: Optional[str] = None


class OrderGetDeleteSchema(Schema):
    id: int


class OrderStatusUpdateSchema(Schema):
    id: int
    status: OrderStatus


class OrderListSchema(Schema):
    status: Optional[OrderStatus] = None
    contract_date_from: Optional[date] = None
    contract_date_to: Optional[date] = None
    from_client: Optional[list[int]] = None
    to_client: Optional[list[int]] = None
    type: Optional[OrderType] = None
    broker: Optional[list[int]] = None
    commodity: Optional[list[int]] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = 100


class OrderSelectSchema(Schema):
    status: Optional[OrderStatus] = None
    from_client: Optional[int] = None
    to_client: Optional[int] = None
    type: Optional[OrderType] = None


class OrderOutSchema(Schema):
    id: int
    type: OrderType
    order_no: Optional[str]
    from_client: Optional[str]
    from_client_id: Optional[int]
    to_client: Optional[str]
    to_client_id: Optional[int]
    commodity: str
    commodity_id: int
    commodity_type: Optional[str]
    rate: Decimal
    quantity: Decimal
    quantity_unit: QuantityUnit
    start_date: Optional[date]
    expiry_date: Optional[date]
    contract_date: Optional[date]
    quantity_fulfilled: Decimal
    broker: Optional[str]
    broker_id: Optional[int]
    status: OrderStatus
    notes: Optional[str]
    is_active: bool


class OrderTransportOutSchema(Schema):
    id: int
    bill_no: Optional[str]
    billing_firm: str
    loading_date: Optional[date]
    unload_date: Optional[date]
    vehicle_no: Optional[str]
    transporter: Optional[str]
    gross_wt_unit: QuantityUnit
    quantity: Decimal
    order_entry: Decimal
    status: str


class OrderDetailOutSchema(OrderOutSchema):
    order_transports: list[OrderTransportOutSchema]


class OrderMutationResponseSchema(Schema):
    success: bool
    message: str
    data: OrderOutSchema


class OrderDetailResponseSchema(Schema):
    success: bool
    data: OrderDetailOutSchema


class OrderPageSchema(Schema):
    page: int
    page_size: int
    total: int
    total_pages: int
    results: list[OrderOutSchema]


class OrderListResponseSchema(Schema):
    success: bool
    data: OrderPageSchema
