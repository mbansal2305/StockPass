from typing import Any, Literal, Optional

from ninja import Schema


EntityType = Literal[
    "broker",
    "businessclient",
    "commodity",
    "transporter",
]


class MasterAddUpdateSchema(Schema):
    entity: EntityType
    content: dict[str, Any]
    id: Optional[int] = None


class MasterGetDeleteSchema(Schema):
    entity: EntityType
    id: int


class MasterListSchema(Schema):
    entity: EntityType
    filters: dict[str, Any] = {}
    page: int = 1
    page_size: int = 10


class MasterSearchSchema(Schema):
    entity: EntityType
    search: str
    filters: dict[str, Any] = {}