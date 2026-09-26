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


class OrderListSchema(Schema):
    status: Optional[OrderStatus] = None
    contract_date_from: Optional[date] = None
    contract_date_to: Optional[date] = None
    from_client: Optional[int] = None
    to_client: Optional[int] = None
    type: Optional[OrderType] = None
    broker: Optional[int] = None
    page: int = 1
    page_size: int = 10


class OrderSelectSchema(Schema):
    status: Optional[OrderStatus] = None
    from_client: Optional[int] = None
    to_client: Optional[int] = None
    type: Optional[OrderType] = None
