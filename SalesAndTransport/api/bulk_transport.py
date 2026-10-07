import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from ninja import Form, Query, Router
from ninja.files import UploadedFile

from SalesAndTransport.models.order import Order
from StockPassCore.auth.permissions import OwnerAdminAuth
from SalesAndTransport.models import BulkTransport, Transport
from SalesAndTransport.schemas.bulk_transport import (
    BulkTransportCreateSchema,
    BulkTransportDeleteResponseSchema,
    BulkTransportDetailResponseSchema,
    BulkTransportGetDeleteSchema,
    BulkTransportListResponseSchema,
    BulkTransportListSchema,
    BulkTransportSearchResponseSchema,
    BulkTransportSearchSchema,
    BulkTransportUpdateSchema,
)
from SalesAndTransport.api.transport import (
    active_order_ids_for_transports,
    apply_transport_fields,
    recalculate_order_fulfillment,
    save_items,
    save_receipt,
    serialize_transport,
    sync_godown_transactions,
    transport_queryset,
    validate_items,
    transport_model_values,
)


router = Router(auth=OwnerAdminAuth())
logger = logging.getLogger("ninja")


def bulk_queryset():
    active_transports = transport_queryset().filter(is_active=True)
    return BulkTransport.objects.select_related(
        "billing_firm",
        "commodity",
        "order",
        "to_client",
        "transporter",
    ).prefetch_related(
        Prefetch("bulk_transport", queryset=active_transports)
    )


def serialize_bulk_transport(bulk_transport: BulkTransport):
    transports = list(bulk_transport.bulk_transport.all())
    return {
        "id": bulk_transport.id,
        "title": bulk_transport.title,
        "loading_date": bulk_transport.loading_date,
        "bill_no": bulk_transport.bill_no,
        "order": bulk_transport.order_id,
        "billing_firm": bulk_transport.billing_firm_id,
        "transporter": bulk_transport.transporter_id,
        "to_client": bulk_transport.to_client_id,
        "commodity": bulk_transport.commodity_id,
        "status": bulk_transport.status,
        "selected_sources": sorted(
            {
                transport.from_client_id
                for transport in transports
                if transport.from_client_id is not None
            }
        ),
        "transports": [
            serialize_transport(transport) for transport in transports
        ],
    }


def serialize_bulk_transport_list_item(bulk_transport: BulkTransport):
    commodity = bulk_transport.commodity
    commodity_name = None
    if commodity:
        commodity_name = commodity.name
        if commodity.type:
            commodity_name += f" ({commodity.type})"

    return {
        "id": bulk_transport.id,
        "loading_date": bulk_transport.loading_date,
        "title": bulk_transport.title,
        "commodity": commodity_name,
        "bill_no": bulk_transport.bill_no,
        "order": bulk_transport.order.order_no if bulk_transport.order else None,
        "billing_firm": (
            bulk_transport.billing_firm.name
            if bulk_transport.billing_firm
            else None
        ),
        "to_client": (
            bulk_transport.to_client.name if bulk_transport.to_client else None
        ),
        "status": bulk_transport.status,
        "num_vehicles": len(bulk_transport.bulk_transport.all()),
    }


def indexed_receipt(request, field_name: str, index: int):
    for key in (
        f"{field_name}_{index}",
        f"transports[{index}].{field_name}",
        f"transports[{index}][{field_name}]",
    ):
        uploaded_file = request.FILES.get(key)
        if uploaded_file is not None:
            return uploaded_file
    return None


def set_transport_receipts(request, values: dict, index: int):
    for field_name, folder in (
        ("wt_rcpt_src", "src_rcpt"),
        ("wt_rcpt_dst", "dst_rcpt"),
    ):
        uploaded_file: UploadedFile | None = indexed_receipt(
            request,
            field_name,
            index,
        )
        url = save_receipt(request, uploaded_file, folder)
        if url is not None:
            values[field_name] = url


def validate_bulk_create(data: BulkTransportCreateSchema):
    if not data.transports:
        raise ValueError("At least one transport is required.")
    for transport_data in data.transports:
        validate_items(transport_data.items, creating=True)
        if len(transport_data.items) != 1:
            raise ValueError("Each transport must have exactly one order item.")


def resolve_bulk_common_values(data, bulk_order=None):
    common_fields = (
        "loading_date",
        "bill_no",
        "order",
        "billing_firm",
        "transporter",
        "to_client",
        "commodity",
        "status",
    )
    if bulk_order is None:
        first_transport = data.transports[0]
        values = {
            "loading_date": first_transport.loading_date,
            "bill_no": first_transport.bill_no,
            "order": first_transport.items[0].order,
            "billing_firm": first_transport.billing_firm,
            "transporter": first_transport.transporter,
            "to_client": first_transport.to_client,
            "commodity": first_transport.commodity,
            "status": first_transport.status,
        }
    else:
        values = {
            "loading_date": bulk_order.loading_date,
            "bill_no": bulk_order.bill_no,
            "order": bulk_order.order_id,
            "billing_firm": bulk_order.billing_firm_id,
            "transporter": bulk_order.transporter_id,
            "to_client": bulk_order.to_client_id,
            "commodity": bulk_order.commodity_id,
            "status": bulk_order.status,
        }

    supplied_values = data.model_dump(
        exclude_unset=True,
        exclude={"id", "title", "transports"},
    )
    values.update(supplied_values)
    return {field: values[field] for field in common_fields}


def save_bulk_common_values(bulk_order, values, user):
    model_values = {}
    for field, value in values.items():
        if field in {"order", "billing_firm", "transporter", "to_client", "commodity"}:
            field = f"{field}_id"
        model_values[field] = value

    for field, value in model_values.items():
        setattr(bulk_order, field, value)
    bulk_order.m_by = user
    bulk_order.full_clean()
    bulk_order.save()


def child_transport_values(transport_data, common_values):
    values = transport_data.model_dump(
        exclude_unset=True,
        exclude={"id", "items"},
    )
    for field, value in common_values.items():
        if field != "order":
            values[field] = value
    return values


def items_with_common_order(transport_data, common_values):
    if common_values["order"] is None:
        return transport_data.items
    return [
        item.model_copy(update={"order": common_values["order"]})
        for item in transport_data.items
    ]


def create_child_transport(
    request,
    bulk_order,
    transport_data,
    common_values,
    index: int,
):
    values = transport_model_values(
        child_transport_values(transport_data, common_values)
    )
    values.setdefault("quantity_unit", "quintal")
    set_transport_receipts(request, values, index)
    transport = Transport(
        **values,
        bulk_transport=bulk_order,
        c_by=request.auth,
    )
    transport.full_clean()
    transport.save()
    items = items_with_common_order(transport_data, common_values)
    save_items(transport, items, request.auth)
    sync_godown_transactions(transport, request.auth)
    return transport


def godown_fields_changed(transport, values):
    relation_fields = {
        "commodity": "commodity_id",
        "from_client": "from_client_id",
        "to_client": "to_client_id",
    }
    for field in ("commodity", "from_client", "to_client", "gross_wt", "gross_wt_unit"):
        if field not in values:
            continue
        model_field = relation_fields.get(field, field)
        if field == "gross_wt_unit":
            model_field = "quantity_unit"
        if getattr(transport, model_field) != values[field]:
            return True
    return False


def update_child_transport(
    request,
    bulk_order,
    transport_data,
    common_values,
    index: int,
):
    transport = get_object_or_404(
        transport_queryset(),
        id=transport_data.id,
        bulk_transport=bulk_order,
        is_active=True,
    )
    active_items = list(transport.items.filter(is_active=True))
    validate_items(transport_data.items, creating=False)
    if len(transport_data.items) != 1:
        raise ValueError("Each transport must have exactly one order item.")

    values = child_transport_values(transport_data, common_values)
    if "gross_wt_unit" in values:
        values["quantity_unit"] = values.pop("gross_wt_unit")
    set_transport_receipts(request, values, index)
    update_godown_ledger = godown_fields_changed(transport, values)
    if update_godown_ledger:
        sync_godown_transactions(
            transport,
            request.auth,
            reverse_existing=True,
            record_current=False,
        )
    apply_transport_fields(transport, values)
    transport.m_by = request.auth
    transport.full_clean()
    transport.save()

    items = items_with_common_order(transport_data, common_values)
    item_data = items[0]
    if item_data.id is None and len(active_items) == 1:
        item_data = item_data.model_copy(update={"id": active_items[0].id})
    save_items(transport, [item_data], request.auth)

    if update_godown_ledger:
        sync_godown_transactions(transport, request.auth)


def delete_child_transport(transport, user):
    sync_godown_transactions(
        transport,
        user,
        reverse_existing=True,
        record_current=False,
    )
    transport.is_active = False
    transport.d_by = user
    transport.save(update_fields=["is_active", "d_by", "m_at"])


def update_bulk_children(request, bulk_order, data, common_values):
    transports = list(
        Transport.objects.filter(
            bulk_transport=bulk_order,
            is_active=True,
        )
    )
    existing_by_id = {transport.id: transport for transport in transports}
    affected_order_ids = active_order_ids_for_transports(
        [transport.id for transport in transports]
    )

    requested_ids = [
        transport_data.id
        for transport_data in data.transports
        if transport_data.id is not None
    ]
    if len(requested_ids) != len(set(requested_ids)):
        raise ValueError("A transport may only be updated once per request.")
    unknown_ids = set(requested_ids) - existing_by_id.keys()
    if unknown_ids:
        raise ValueError("A transport in this bulk transport was not found.")

    retained_ids = set()
    for index, transport_data in enumerate(data.transports):
        if transport_data.id is None:
            transport = create_child_transport(
                request,
                bulk_order,
                transport_data,
                common_values,
                index,
            )
        else:
            transport = existing_by_id[transport_data.id]
            update_child_transport(
                request,
                bulk_order,
                transport_data,
                common_values,
                index,
            )
        retained_ids.add(transport.id)

    for transport in transports:
        if transport.id not in retained_ids:
            delete_child_transport(transport, request.auth)

    recalculate_order_fulfillment(affected_order_ids, request.auth)


@router.post(
    "/add",
    response={200: BulkTransportDetailResponseSchema, 400: dict},
)
@transaction.atomic
def add_bulk_transport(request, data: Form[BulkTransportCreateSchema]):
    try:
        validate_bulk_create(data)
        common_values = resolve_bulk_common_values(data)
        bulk_order = BulkTransport(title=data.title, c_by=request.auth)
        save_bulk_common_values(bulk_order, common_values, request.auth)

        for index, transport_data in enumerate(data.transports):
            create_child_transport(
                request,
                bulk_order,
                transport_data,
                common_values,
                index,
            )

        bulk_order = bulk_queryset().get(id=bulk_order.id)
        return {"success": True, "data": serialize_bulk_transport(bulk_order)}
    except Exception as error:
        if settings.DEBUG:
            logger.exception("Bulk transport request failed")
        return 400, {"success": False, "message": str(error)}


@router.patch(
    "/upd",
    response={200: BulkTransportDetailResponseSchema, 400: dict},
)
@transaction.atomic
def update_bulk_transport(request, data: Form[BulkTransportUpdateSchema]):
    try:
        bulk_order = get_object_or_404(
            BulkTransport,
            id=data.id,
            is_active=True,
        )
        common_values = resolve_bulk_common_values(data, bulk_order)
        if data.title is not None:
            bulk_order.title = data.title
        save_bulk_common_values(bulk_order, common_values, request.auth)
        update_bulk_children(request, bulk_order, data, common_values)

        bulk_order = bulk_queryset().get(id=bulk_order.id)
        return {"success": True, "data": serialize_bulk_transport(bulk_order)}
    except Exception as error:
        if settings.DEBUG:
            logger.exception("Bulk transport request failed")
        return 400, {"success": False, "message": str(error)}


@router.get(
    "/get",
    response={200: BulkTransportDetailResponseSchema},
)
def get_bulk_transport(request, data: Query[BulkTransportGetDeleteSchema]):
    bulk_order = get_object_or_404(
        bulk_queryset(),
        id=data.id,
        is_active=True,
    )
    return {"success": True, "data": serialize_bulk_transport(bulk_order)}


@router.delete(
    "/del",
    response={200: BulkTransportDeleteResponseSchema},
)
@transaction.atomic
def delete_bulk_transport(request, data: BulkTransportGetDeleteSchema):
    bulk_order = get_object_or_404(BulkTransport, id=data.id, is_active=True)
    transports = list(
        Transport.objects.filter(
            bulk_transport=bulk_order,
            is_active=True,
        )
    )
    affected_order_ids = active_order_ids_for_transports(
        [transport.id for transport in transports]
    )
    bulk_order.is_active = False
    bulk_order.d_by = request.auth
    bulk_order.save(update_fields=["is_active", "d_by"])

    for transport in transports:
        transport.is_active = False
        transport.d_by = request.auth
        transport.save(update_fields=["is_active", "d_by"])

    recalculate_order_fulfillment(affected_order_ids, request.auth)
    return {"success": True, "id": bulk_order.id}


@router.post(
    "/lst",
    response={200: BulkTransportListResponseSchema, 400: dict},
)
def list_bulk_transports(request, data: Form[BulkTransportListSchema]):
    if data.page < 1 or data.page_size < 1 or data.page_size > 100:
        return 400, {"success": False, "message": "Invalid pagination values."}

    queryset = bulk_queryset().filter(is_active=True).order_by("id")
    total = queryset.count()
    start = (data.page - 1) * data.page_size
    bulk_orders = queryset[start : start + data.page_size]
    return {
        "success": True,
        "data": {
            "page": data.page,
            "page_size": data.page_size,
            "total": total,
            "total_pages": (total + data.page_size - 1) // data.page_size,
            "results": [
                serialize_bulk_transport_list_item(item) for item in bulk_orders
            ],
        },
    }


@router.post(
    "/search",
    response={200: BulkTransportSearchResponseSchema},
)
def search_bulk_transports(request, data: Form[BulkTransportSearchSchema]):
    queryset = bulk_queryset().filter(
        is_active=True,
        title__icontains=data.title.strip(),
    ).order_by("title", "id")
    return {
        "success": True,
        "total": queryset.count(),
        "results": [serialize_bulk_transport(item) for item in queryset],
    }




@router.get("/orders/sel/", response={200: dict})
def select_purchase_orders(request):
    orders = Order.objects.filter(
        is_active=True,
        status__in=[Order.OrderStatus.PENDING, Order.OrderStatus.DRAFT],
    ).select_related(
        "commodity",
        "from_client",
        "to_client",
    ).order_by("order_no", "id")

    return {
        "success": True,
        "data": [
            {
                "id": order.id,
                "order_type": order.type,
                "status": order.status,
                "order_number": order.order_no,
                "commodity": order.commodity.name,
                "commodity_type" : order.commodity.type,
                "commodity_id" : order.commodity.id,
                "order_qty" : order.quantity,
                "rem_qty" : (order.quantity - order.quantity_fulfilled),
                "qty_unit" : order.quantity_unit,
                "from_client": (
                    order.from_client.name
                    if order.type == Order.OrderType.PURCHASE_ORDER
                    and order.from_client
                    else None
                ),
                "to_client": (
                    order.to_client.name
                    if order.type == Order.OrderType.SALES_ORDER
                    and order.to_client
                    else None
                ),
            }
            for order in orders
        ],
    }
