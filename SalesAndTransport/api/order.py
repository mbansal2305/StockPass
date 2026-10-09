import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Query, Router

from StockPassCore.auth.permissions import OwnerAdminAuth
from SalesAndTransport.models import (
    BusinessClient,
    Order,
    PurchaseOrderSequence,
    TransportItems,
)
from SalesAndTransport.api.transport import recalculate_order_fulfillment
from SalesAndTransport.schemas.order import (
    OrderCreateSchema,
    OrderDetailResponseSchema,
    OrderListSchema,
    OrderListResponseSchema,
    OrderMutationResponseSchema,
    OrderSelectSchema,
    OrderStatusUpdateSchema,
    OrderUpdateSchema,
    OrderGetDeleteSchema,
)


router = Router(auth=OwnerAdminAuth())
logger = logging.getLogger("ninja")

def serialize_order(order: Order):
    return {
        "id": order.id,
        "type": order.type,
        "order_no": order.order_no,
        "from_client": order.from_client.name if order.from_client else None,
        "from_client_id": order.from_client_id,
        "to_client": order.to_client.name if order.to_client else None,
        "to_client_id": order.to_client_id,
        "commodity": order.commodity.name,
        "commodity_id": order.commodity_id,
        "commodity_type" : order.commodity.type,
        "rate": order.rate,
        "quantity": order.quantity,
        "quantity_unit": order.quantity_unit,
        "start_date": order.start_date,
        "expiry_date": order.expiry_date,
        "contract_date": order.contract_date,
        "quantity_fulfilled": order.quantity_fulfilled,
        "broker": order.broker.name if order.broker else None,
        "broker_id": order.broker_id,
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
        "id" : order.id
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
        exclude={
            "page",
            "page_size",
            "contract_date_from",
            "contract_date_to",
            "from_client",
            "to_client",
            "broker",
            "commodity",
            "search",
        },
    )

    for field in ("from_client", "to_client", "broker", "commodity"):
        values = getattr(data, field)
        if values is not None:
            filters[f"{field}_id__in"] = values

    contract_date_from = getattr(data, "contract_date_from", None)
    contract_date_to = getattr(data, "contract_date_to", None)

    if contract_date_from is not None:
        filters["contract_date__gte"] = contract_date_from
    if contract_date_to is not None:
        filters["contract_date__lte"] = contract_date_to

    search = getattr(data, "search", None)
    if search:
        filters["order_no__icontains"] = search

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


def client_selection(client_type: str):
    return list(
        BusinessClient.objects.filter(
            is_active=True,
            type=client_type,
        )
        .order_by("name", "id")
        .values("id", "name", "type", "city")
    )


def highest_purchase_order_serial(year: int) -> int:
    prefix = f"PO-{year}-"
    order_numbers = Order.objects.filter(
        type=Order.OrderType.PURCHASE_ORDER,
        order_no__startswith=prefix,
    ).values_list("order_no", flat=True)
    serials = [
        int(suffix)
        for order_number in order_numbers
        if (suffix := order_number[len(prefix):]).isdigit()
    ]
    return max(serials, default=0)


def next_purchase_order_serial(year: int, starting_serial: int) -> int:
    prefix = f"PO-{year}-"
    serial = max(starting_serial, highest_purchase_order_serial(year) + 1)
    while Order.objects.filter(
        type=Order.OrderType.PURCHASE_ORDER,
        order_no=f"{prefix}{serial:04d}",
    ).exists():
        serial += 1
    return serial


def allocate_purchase_order_number() -> str:
    year = timezone.localdate().year
    sequence, _ = PurchaseOrderSequence.objects.get_or_create(
        year=year,
        defaults={"next_serial": highest_purchase_order_serial(year) + 1},
    )
    sequence = PurchaseOrderSequence.objects.select_for_update().get(year=year)
    serial = next_purchase_order_serial(year, sequence.next_serial)
    sequence.next_serial = serial + 1
    sequence.save(update_fields=["next_serial"])
    return f"PO-{year}-{serial:04d}"


@router.get("/ordernum/po/", response={200: dict})
def generate_purchase_order_number(request):
    year = timezone.localdate().year
    sequence = PurchaseOrderSequence.objects.filter(year=year).first()
    starting_serial = sequence.next_serial if sequence else 1
    serial = next_purchase_order_serial(year, starting_serial)

    return {
        "success": True,
        "data": {"order_no": f"PO-{year}-{serial:04d}"},
    }


@router.get("/so/clients/sel/", response={200: dict})
def select_sales_order_clients(request):
    return {
        "success": True,
        "data": {
            "from_client": client_selection(BusinessClient.ClientType.MY_FIRM),
            "to_client": client_selection(BusinessClient.ClientType.COMPANY),
        },
    }


@router.get("/po/clients/sel/", response={200: dict})
def select_purchase_order_clients(request):
    return {
        "success": True,
        "data": {
            "from_client": client_selection(BusinessClient.ClientType.COMPANY),
            "to_client": client_selection(BusinessClient.ClientType.MY_FIRM),
        },
    }


@router.post("/add/", response={200: OrderMutationResponseSchema, 400: dict})
@transaction.atomic
def add_order(request, data: OrderCreateSchema):
    try:
        order_data = data.model_dump(exclude_unset=True)
        if order_data.get("type") == Order.OrderType.PURCHASE_ORDER:
            order_data["order_no"] = allocate_purchase_order_number()

        for field in ("from_client", "to_client", "commodity", "broker"):
            if field in order_data:
                order_data[f"{field}_id"] = order_data.pop(field)

        order = Order(
            **order_data,
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
        if settings.DEBUG:
            logger.exception("Order request failed")
        return 400, {"success": False, "message": str(error)}


@router.patch("/upd/", response={200: OrderMutationResponseSchema, 400: dict})
@transaction.atomic
def update_order(request, data: OrderUpdateSchema):
    try:
        order = get_object_or_404(Order, id=data.id, is_active=True)

        values = data.model_dump(
            exclude_unset=True,
            exclude={"id"},
        )
        quantity_unit_changed = (
            "quantity_unit" in values
            and values["quantity_unit"] != order.quantity_unit
        )
        for field, value in values.items():
            if field in {"from_client", "to_client", "commodity", "broker"}:
                field = f"{field}_id"
            setattr(order, field, value)

        order.m_by = request.auth
        order.full_clean()
        order.save()

        if quantity_unit_changed:
            recalculate_order_fulfillment({order.id}, request.auth)
            order.refresh_from_db(fields=["quantity_fulfilled"])

        return {
            "success": True,
            "message": "order updated successfully.",
            "data": serialize_order(order),
        }
    except Exception as error:
        if settings.DEBUG:
            logger.exception("Order request failed")
        return 400, {"success": False, "message": str(error)}


@router.patch("/status/upd/", response={200: dict})
@transaction.atomic
def update_order_status(request, data: OrderStatusUpdateSchema):
    order = get_object_or_404(Order, id=data.id, is_active=True)
    order.status = data.status
    order.m_by = request.auth
    order.save(update_fields=["status", "m_by", "m_at"])

    return {
        "success": True,
        "message": "order status updated successfully.",
        "data": {"id": order.id, "status": order.status},
    }


@router.get("/get/", response=OrderDetailResponseSchema)
def get_order(request, data: Query[OrderGetDeleteSchema]):
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
    order_data = serialize_order(order)
    order_data["order_transports"] = [
        {
            "id": item.transport.id,
            "bill_no": item.transport.bill_no,
            "billing_firm": item.transport.billing_firm.name,
            "loading_date": item.transport.loading_date,
            "unload_date": item.transport.unload_date,
            "vehicle_no": item.transport.vehicle_no,
            "transporter": (
                item.transport.transporter.name
                if item.transport.transporter
                else None
            ),
            "gross_wt_unit": item.transport.quantity_unit,
            "quantity": item.quantity,
            "order_entry": item.order_quantity,
            "status": item.transport.status,
        }
        for item in TransportItems.objects.filter(
            order=order,
            is_active=True,
            transport__is_active=True,
        )
        .select_related(
            "transport__billing_firm",
            "transport__transporter",
        )
        .order_by("transport_id", "id")
    ]
    return {
        "success": True,
        "data": order_data,
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


@router.post("/lst/", response={200: OrderListResponseSchema, 400: dict})
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

