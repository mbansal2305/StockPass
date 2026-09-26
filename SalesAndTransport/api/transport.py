from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Prefetch, Q
from django.forms import ImageField
from django.shortcuts import get_object_or_404
from ninja import File, Form, Router
from ninja.files import UploadedFile

from StockPassCore.auth.permissions import OwnerAdminAuth
from SalesAndTransport.models import (
    Order,
    Transport,
    TransportItems,
)
from SalesAndTransport.schemas.transport import (
    TransportCreateSchema,
    TransportDeleteResponseSchema,
    TransportDetailResponseSchema,
    TransportGetDeleteSchema,
    TransportItemInputSchema,
    TransportListResponseSchema,
    TransportListSchema,
    TransportSearchResponseSchema,
    TransportSearchSchema,
    TransportUpdateSchema,
)


router = Router(auth=OwnerAdminAuth())


def serialize_transport_item(item: TransportItems):
    return {
        "id": item.id,
        "order": item.order.order_no if item.order else None,
        "quantity": item.quantity,
    }


def serialize_transport(transport: Transport):
    return {
        "id": transport.id,
        "billing_firm": transport.billing_firm.name,
        "bill_no": transport.bill_no,
        "bulk_transport": (
            transport.bulk_transport.title if transport.bulk_transport else None
        ),
        "commodity": transport.commodity.name,
        "from_client": transport.from_client.name if transport.from_client else None,
        "to_client": transport.to_client.name if transport.to_client else None,
        "gross_wt": transport.gross_wt,
        "gross_wt_unit": transport.quantity_unit,
        "bag_nos": transport.bag_nos,
        "bag_wt": transport.bag_wt,
        "vehicle_no": transport.vehicle_no,
        "transporter": transport.transporter.name if transport.transporter else None,
        "anugya": transport.anugya,
        "gatepass": transport.gatepass,
        "unload_date": transport.unload_date,
        "rcvd_wt": transport.rcvd_wt,
        "rent": transport.rent,
        "adv_by_client": transport.adv_by_client,
        "adv_by_firm": transport.adv_by_firm,
        "final_paid": transport.final_paid,
        "status": transport.status,
        "wt_rcpt_src": transport.wt_rcpt_src,
        "wt_rcpt_dst": transport.wt_rcpt_dst,
        "items": [serialize_transport_item(item) for item in transport.items.all()],
    }


def transport_queryset():
    active_items = TransportItems.objects.filter(is_active=True).select_related("order")
    return Transport.objects.select_related(
        "billing_firm",
        "bulk_transport",
        "commodity",
        "from_client",
        "to_client",
        "transporter",
    ).prefetch_related(Prefetch("items", queryset=active_items))


def save_receipt(request, uploaded_file: UploadedFile | None, folder: str):
    if uploaded_file is None:
        return None

    try:
        ImageField().clean(uploaded_file)
    except ValidationError as error:
        raise ValueError(str(error)) from error

    extension = Path(uploaded_file.name).suffix.lower()
    storage_path = f"transport/{folder}/{uuid4().hex}{extension}"
    saved_path = default_storage.save(storage_path, uploaded_file)
    return request.build_absolute_uri(default_storage.url(saved_path))


def validate_items(items: list[TransportItemInputSchema], creating: bool):
    if not items:
        raise ValueError("At least one transport item is required.")
    if creating and any(item.id is not None for item in items):
        raise ValueError("item id must not be provided when adding a transport.")


def apply_transport_fields(transport: Transport, values: dict):
    for field, value in values.items():
        if field == "gross_wt_unit":
            field = "quantity_unit"
        setattr(transport, field, value)


def save_items(transport: Transport, items: list[TransportItemInputSchema], user):
    for item_data in items:
        values = item_data.model_dump(exclude_unset=True, exclude={"id"})
        order_id = values.pop("order")
        order = get_object_or_404(Order, id=order_id, is_active=True)
        item_id = item_data.id

        if item_id is None:
            TransportItems.objects.create(
                transport=transport,
                order=order,
                quantity=values.get("quantity") or 0,
                c_by=user,
            )
            continue

        transport_item = get_object_or_404(
            TransportItems,
            id=item_id,
            transport=transport,
            is_active=True,
        )
        transport_item.order = order
        if "quantity" in values and values["quantity"] is not None:
            transport_item.quantity = values["quantity"]
        transport_item.m_by = user
        transport_item.save()


@router.post("/add", response={200: TransportDetailResponseSchema, 400: dict})
@transaction.atomic
def add_transport(
    request,
    data: Form[TransportCreateSchema],
    wt_rcpt_src: File[UploadedFile | None] = None,
    wt_rcpt_dst: File[UploadedFile | None] = None,
):
    try:
        validate_items(data.items, creating=True)
        values = data.model_dump(exclude_unset=True, exclude={"items"})
        values["quantity_unit"] = values.pop("gross_wt_unit", "quintal")
        src_url = save_receipt(request, wt_rcpt_src, "src_rcpt")
        dst_url = save_receipt(request, wt_rcpt_dst, "dst_rcpt")
        if src_url is not None:
            values["wt_rcpt_src"] = src_url
        if dst_url is not None:
            values["wt_rcpt_dst"] = dst_url

        transport = Transport(**values, c_by=request.auth)
        transport.bulk_transport = None
        transport.full_clean()
        transport.save()
        save_items(transport, data.items, request.auth)

        return {"success": True, "data": serialize_transport(transport)}
    except Exception as error:
        return 400, {"success": False, "message": str(error)}


@router.patch("/upd", response={200: TransportDetailResponseSchema, 400: dict})
@transaction.atomic
def update_transport(
    request,
    data: Form[TransportUpdateSchema],
    wt_rcpt_src: File[UploadedFile | None] = None,
    wt_rcpt_dst: File[UploadedFile | None] = None,
):
    try:
        transport = get_object_or_404(
            transport_queryset(),
            id=data.id,
            is_active=True,
        )
        if data.items is not None:
            validate_items(data.items, creating=False)

        values = data.model_dump(exclude_unset=True, exclude={"id", "items"})
        src_url = save_receipt(request, wt_rcpt_src, "src_rcpt")
        dst_url = save_receipt(request, wt_rcpt_dst, "dst_rcpt")
        if src_url is not None:
            values["wt_rcpt_src"] = src_url
        if dst_url is not None:
            values["wt_rcpt_dst"] = dst_url

        apply_transport_fields(transport, values)
        transport.m_by = request.auth
        transport.full_clean()
        transport.save()

        if data.items is not None:
            save_items(transport, data.items, request.auth)

        transport = transport_queryset().get(id=transport.id)
        return {"success": True, "data": serialize_transport(transport)}
    except Exception as error:
        return 400, {"success": False, "message": str(error)}


@router.get("/get", response={200: TransportDetailResponseSchema})
def get_transport(request, data: TransportGetDeleteSchema):
    transport = get_object_or_404(
        transport_queryset(),
        id=data.id,
        is_active=True,
    )
    return {"success": True, "data": serialize_transport(transport)}


@router.delete("/del", response={200: TransportDeleteResponseSchema})
@transaction.atomic
def delete_transport(request, data: TransportGetDeleteSchema):
    transport = get_object_or_404(Transport, id=data.id, is_active=True)
    transport.is_active = False
    transport.d_by = request.auth
    transport.save(update_fields=["is_active", "d_by"])
    return {"success": True, "id": transport.id}


@router.post("/lst", response={200: TransportListResponseSchema, 400: dict})
def list_transports(request, data: Form[TransportListSchema]):
    if data.page < 1 or data.page_size < 1 or data.page_size > 100:
        return 400, {"success": False, "message": "Invalid pagination values."}

    filters = {
        key: value
        for key, value in data.model_dump(
            exclude_none=True,
            exclude={"page", "page_size"},
        ).items()
    }
    queryset = transport_queryset().filter(is_active=True, **filters).order_by("id")
    total = queryset.count()
    start = (data.page - 1) * data.page_size
    transports = queryset[start : start + data.page_size]
    return {
        "success": True,
        "data": {
            "page": data.page,
            "page_size": data.page_size,
            "total": total,
            "total_pages": (total + data.page_size - 1) // data.page_size,
            "results": [serialize_transport(transport) for transport in transports],
        },
    }


@router.post("/search", response={200: TransportSearchResponseSchema})
def search_transports(request, data: Form[TransportSearchSchema]):
    keyword = data.keyword.strip()
    queryset = transport_queryset().filter(is_active=True)
    if keyword:
        queryset = queryset.filter(
            Q(bill_no__icontains=keyword) | Q(vehicle_no__icontains=keyword)
        )
    queryset = queryset.order_by("bill_no", "id")
    return {
        "success": True,
        "total": queryset.count(),
        "results": [serialize_transport(transport) for transport in queryset],
    }