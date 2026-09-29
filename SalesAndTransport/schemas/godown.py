from decimal import Decimal
from typing import Literal

from ninja import Schema


QuantityUnit = Literal["mt", "quintal", "kg"]
GodownTransactionType = Literal["entry", "exit", "reversal"]


class GodownTransactionCreateSchema(Schema):
    godown: int
    commodity: int
    quantity: Decimal
    quantity_unit: QuantityUnit = "quintal"


class GodownTransactionUpdateSchema(GodownTransactionCreateSchema):
    id: int


class GodownTransactionDeleteSchema(Schema):
    id: int


class GodownTransactionListSchema(Schema):
    godown: int | None = None
    commodity: int | None = None
    transaction_type: GodownTransactionType | None = None
    time_range: str | None = None
    page: int = 1
    page_size: int = 20