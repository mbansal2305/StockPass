import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from ninja import Form, Router
from ninja.files import UploadedFile

from StockPassCore.auth.permissions import OwnerAdminAuth
from SalesAndTransport.models import BulkTransport, Transport, TransportItems
from SalesAndTransport.schemas.bulk_transport import (
    BulkTransportCreateSchema,
    BulkTransportDeleteResponseSchema,
    BulkTransportDetailResponseSchema,
    BulkTransportGetDeleteSchema,
    BulkTransportListResponseSchema,
    BulkTransportListSchema,
    BulkTransportOutSchema,
    BulkTransportSearchResponseSchema,
    BulkTransportSearchSchema,
    BulkTransportUpdateSchema,
)
from SalesAndTransport.schemas.transport import TransportItemInputSchema
from SalesAndTransport.api.transport import (
    active_order_ids_for_transports,
    apply_transport_fields,
    recalculate_order_fulfillment,
    recalculate_transport_order_fulfillment,
    save_items,
    save_receipt,
    serialize_transport,
    transport_queryset,
    validate_items,
    transport_model_values,
)


router = Router(auth=OwnerAdminAuth())
logger = logging.getLogger("ninja")


def bulk_queryset():
    active_transports = transport_queryset().filter(is_active=True)
    return BulkTransport.objects.prefetch_related(
        Prefetch("transports", queryset=active_transports)
    )


def serialize_bulk_transport(bulk_transport: BulkTransport):
    return {
        "id": bulk_transport.id,
        "title": bulk_transport.title,
        "transports": [
            serialize_transport(transport)
            for transport in bulk_transport.transports.all()
        ],
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


def create_child_transport(request, bulk_order, transport_data, index: int):
    values = transport_model_values(
        transport_data.model_dump(exclude_unset=True, exclude={"items"})
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
    save_items(transport, transport_data.items, request.auth)
    return transport


def update_child_transport(request, bulk_order, transport_data, index: int):
    transport = get_object_or_404(
        transport_queryset(),
        id=transport_data.id,
        bulk_transport=bulk_order,
        is_active=True,
    )
    active_items = list(transport.items.filter(is_active=True))
    if transport_data.items is not None:
        validate_items(transport_data.items, creating=False)
        if len(transport_data.items) != 1:
            raise ValueError("Each transport must have exactly one order item.")
    elif len(active_items) != 1:
        raise ValueError("Each transport must have exactly one active order item.")

    values = transport_data.model_dump(exclude_unset=True, exclude={"id", "items"})
    if "gross_wt_unit" in values:
        values["quantity_unit"] = values.pop("gross_wt_unit")
    set_transport_receipts(request, values, index)
    apply_transport_fields(transport, values)
    transport.m_by = request.auth
    transport.full_clean()
    transport.save()

    if transport_data.items is not None:
        item_data = transport_data.items[0]
        if item_data.id is None and len(active_items) == 1:
            item_data = TransportItemInputSchema(
                id=active_items[0].id,
                order=item_data.order,
                quantity=item_data.quantity,
                order_entry=item_data.order_entry,
            )
        save_items(transport, [item_data], request.auth)
    else:
        recalculate_transport_order_fulfillment(
            [transport.id],
            request.auth,
        )


@router.post(
    "/add",
    response={200: BulkTransportDetailResponseSchema, 400: dict},
)
@transaction.atomic
def add_bulk_transport(request, data: Form[BulkTransportCreateSchema]):
    try:
        validate_bulk_create(data)
        bulk_order = BulkTransport(title=data.title, c_by=request.auth)
        bulk_order.full_clean()
        bulk_order.save()

        for index, transport_data in enumerate(data.transports):
            create_child_transport(request, bulk_order, transport_data, index)

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
        if data.title is not None:
            bulk_order.title = data.title
        bulk_order.m_by = request.auth
        bulk_order.full_clean()
        bulk_order.save()

        if data.transports is not None:
            transport_ids = [transport.id for transport in data.transports]
            if len(transport_ids) != len(set(transport_ids)):
                raise ValueError("A transport may only be updated once per request.")
            for index, transport_data in enumerate(data.transports):
                update_child_transport(request, bulk_order, transport_data, index)

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
def get_bulk_transport(request, data: BulkTransportGetDeleteSchema):
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
            "results": [serialize_bulk_transport(item) for item in bulk_orders],
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