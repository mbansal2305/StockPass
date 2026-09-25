from typing import Any

from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja import Router

from StockPassCore.auth.permissions import OwnerAdminAuth
from SalesAndTransport.models import Order
from SalesAndTransport.schemas.order import (
    OrderCreateSchema,
    OrderListSchema,
    OrderSelectSchema,
    OrderUpdateSchema,
    OrderGetDeleteSchema,
)


router = Router(auth=OwnerAdminAuth())

def serialize_order(order: Order):
    return {
        "id": order.id,
        "type": order.type,
        "order_no": order.order_no,
        "from_client": order.from_client.name if order.from_client else None,
        "to_client": order.to_client.name if order.to_client else None,
        "commodity": order.commodity.name,
        "rate": order.rate,
        "quantity": order.quantity,
        "quantity_unit": order.quantity_unit,
        "start_date": order.start_date,
        "expiry_date": order.expiry_date,
        "contract_date": order.contract_date,
        "quantity_fulfilled": order.quantity_fulfilled,
        "broker": order.broker.name if order.broker else None,
        "status": order.status,
        "notes": order.notes,
        "is_active": order.is_active,
    }


def serialize_order_selection(order: Order):
    return {
        "status": order.status,
        "order_no": order.order_no,
        "from_client": order.from_client.name if order.from_client else None,
        "to_client": order.to_client.name if order.to_client else None,
        "type": order.type,
        "commodity": order.commodity.name,
    }


def paginate_queryset(queryset, page: int, page_size: int, serializer):
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")
    if page_size > 100:
        raise ValueError("page_size cannot be greater than 100")

    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "results": [serializer(order) for order in queryset[start:end]],
    }


def get_filters(data):
    filters = data.model_dump(
        exclude_none=True,
        exclude={"page", "page_size", "contract_date_from", "contract_date_to"},
    )

    contract_date_from = getattr(data, "contract_date_from", None)
    contract_date_to = getattr(data, "contract_date_to", None)

    if contract_date_from is not None:
        filters["contract_date__gte"] = contract_date_from
    if contract_date_to is not None:
        filters["contract_date__lte"] = contract_date_to

    return filters


def active_orders(filters: dict[str, Any]):
    return Order.objects.filter(
        is_active=True,
        **filters,
    ).select_related(
        "from_client",
        "to_client",
        "commodity",
        "broker",
    )


@router.post("/add/")
@transaction.atomic
def add_order(request, data: OrderCreateSchema):
    try:
        order = Order(
            **data.model_dump(exclude_unset=True),
            c_by=request.auth,
        )
        order.full_clean()
        order.save()

        return {
            "success": True,
            "message": "order created successfully.",
            "data": serialize_order(order),
        }
    except Exception as error:
        return 400, {"success": False, "message": str(error)}


@router.patch("/upd/")
@transaction.atomic
def update_order(request, data: OrderUpdateSchema):
    try:
        order = get_object_or_404(Order, id=data.id, is_active=True)

        for field, value in data.model_dump(
            exclude_unset=True,
            exclude={"id"},
        ).items():
            setattr(order, field, value)

        order.m_by = request.auth
        order.full_clean()
        order.save()

        return {
            "success": True,
            "message": "order updated successfully.",
            "data": serialize_order(order),
        }
    except Exception as error:
        return 400, {"success": False, "message": str(error)}


@router.get("/get/")
def get_order(request, data: OrderGetDeleteSchema):
    order = get_object_or_404(
        Order.objects.select_related(
            "from_client",
            "to_client",
            "commodity",
            "broker",
        ),
        id=data.id,
        is_active=True,
    )
    return {
        "success": True,
        "data": serialize_order(order),
    }


@router.delete("/del/")
@transaction.atomic
def delete_order(request, data: OrderGetDeleteSchema):
    order = get_object_or_404(Order, id=data.id, is_active=True)
    order.is_active = False
    order.d_by = request.auth
    order.save(update_fields=["is_active", "d_by"])

    return {
        "success": True,
        "message": "order deleted successfully.",
        "id": order.id,
    }


@router.post("/lst/")
def list_orders(request, data: OrderListSchema):
    try:
        queryset = active_orders(get_filters(data)).order_by("id")
        return {
            "success": True,
            "data": paginate_queryset(
                queryset,
                data.page,
                data.page_size,
                serialize_order,
            ),
        }
    except ValueError as error:
        return 400, {"success": False, "message": str(error)}


@router.post("/sel/")
def select_orders(request, data: OrderSelectSchema):
    try:
        queryset = active_orders(get_filters(data)).order_by("order_no", "id")
        return {
            "success": True,
            "data": [
                serialize_order_selection(order)
                for order in queryset
            ],
        }
    except ValueError as error:
        return 400, {"success": False, "message": str(error)}