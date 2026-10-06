import base64
import logging
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Prefetch, Q
from django.forms import ImageField
from django.shortcuts import get_object_or_404
from ninja import File, Form, Query, Router
from ninja.files import UploadedFile

from StockPassCore.auth.permissions import OwnerAdminAuth
from SalesAndTransport.models import (
    BusinessClient,
    BusinessClientProfilePicture,
    GodownTransaction,
    Order,
    Transport,
    TransportItems,
    Transporter,
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
logger = logging.getLogger("ninja")


TRANSPORT_FOREIGN_KEY_FIELDS = {
    "billing_firm",
    "commodity",
    "from_client",
    "to_client",
    "transporter",
}


def transport_model_values(values: dict):
    model_values = {}
    for field, value in values.items():
        if field == "gross_wt_unit":
            field = "quantity_unit"
        elif field in TRANSPORT_FOREIGN_KEY_FIELDS:
            field = f"{field}_id"
        model_values[field] = value
    return model_values





def serialize_transport_item(item: TransportItems):
    return {
        "id": item.id,
        "order_id": item.order_id,
        "order": item.order.order_no if item.order else None,
        "quantity": item.quantity,
        "order_entry": item.order_quantity,
    }


def serialize_billing_firm_image(billing_firm: BusinessClient) -> str | None:
    pictures = getattr(billing_firm, "active_profile_pictures", [])
    if not pictures:
        return None

    filename = Path(urlsplit(pictures[0].url).path).name
    if not filename:
        raise ValueError("Billing firm profile picture has an invalid URL.")

    with default_storage.open(f"profile_picture/{filename}", "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("ascii")


def serialize_transport(transport: Transport, include_billing_firm_image: bool = False):
    data = {
        "id": transport.id,
        "billing_firm": transport.billing_firm.name,
        "bill_no": transport.bill_no,
        "bulk_transport": (
            transport.bulk_transport.title if transport.bulk_transport else None
        ),
        "commodity": transport.commodity.name,
        "commodity_type": transport.commodity.type,
        "loading_date" : transport.loading_date,
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
        "rent_type": transport.rent_type,
        "rent": transport.rent,
        "adv_by_client": transport.adv_by_client,
        "adv_by_firm": transport.adv_by_firm,
        "final_paid" : transport.final_paid,
        "extra_paid": transport.extra_paid,
        "shortage" : transport.shortage,
        "status": transport.status,
        "notes": transport.notes,
        "wt_rcpt_src": transport.wt_rcpt_src,
        "wt_rcpt_dst": transport.wt_rcpt_dst,
        "items": [serialize_transport_item(item) for item in transport.items.all()],
    }

    if include_billing_firm_image:
        data["image"] = serialize_billing_firm_image(transport.billing_firm)

    return data


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
    if creating and not items:
        raise ValueError("At least one transport item is required.")
    if creating and any(item.id is not None for item in items):
        raise ValueError("item id must not be provided when adding a transport.")


def apply_transport_fields(transport: Transport, values: dict):
    for field, value in transport_model_values(values).items():
        setattr(transport, field, value)


def save_items(transport: Transport, items: list[TransportItemInputSchema], user):
    affected_order_ids = active_order_ids_for_transports([transport.id])
    retained_item_ids = set()
    for item_data in items:
        values = item_data.model_dump(exclude_unset=True, exclude={"id"})
        order_id = values.pop("order")
        order = get_object_or_404(Order, id=order_id, is_active=True)
        item_id = item_data.id

        if item_id is None:
            transport_item = TransportItems.objects.create(
                transport=transport,
                order=order,
                quantity=values.get("quantity") or 0,
                order_quantity=values.get("order_entry") or 0,
                c_by=user,
            )
            retained_item_ids.add(transport_item.id)
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

        if "order_entry" in values and values["order_entry"] is not None:
            transport_item.order_quantity = values["order_entry"]
        transport_item.m_by = user
        transport_item.save()
        retained_item_ids.add(transport_item.id)

    TransportItems.objects.filter(
        transport=transport,
        is_active=True,
    ).exclude(
        id__in=retained_item_ids,
    ).update(
        is_active=False,
        d_by=user,
    )

    affected_order_ids.update(active_order_ids_for_transports([transport.id]))
    recalculate_order_fulfillment(affected_order_ids, user)


def quantity_in_quintals(quantity: Decimal, unit: str) -> Decimal:
    if unit == "mt":
        return quantity * Decimal("10")
    if unit == "kg":
        return quantity / Decimal("100")
    if unit == "quintal":
        return quantity
    raise ValueError(f"Unsupported quantity unit: {unit}")


def active_order_ids_for_transports(transport_ids: list[int]) -> set[int]:
    return set(
        TransportItems.objects.filter(
            transport_id__in=transport_ids,
            transport__is_active=True,
            is_active=True,
        )
        .exclude(order_id__isnull=True)
        .values_list("order_id", flat=True)
        .distinct()
    )


def recalculate_transport_order_fulfillment(
    transport_ids: list[int],
    user=None,
):
    recalculate_order_fulfillment(
        active_order_ids_for_transports(transport_ids),
        user,
    )


def recalculate_order_fulfillment(order_ids: set[int], user=None):
    if not order_ids:
        return

    orders = list(
        Order.objects.select_for_update()
        .filter(id__in=order_ids)
        .order_by("id")
    )
    if not orders:
        return

    fulfilled_in_quintals = {order.id: Decimal("0") for order in orders}
    for item in TransportItems.objects.filter(
        order_id__in=fulfilled_in_quintals,
        transport__is_active=True,
        is_active=True,
    ).select_related("transport"):
        fulfilled_in_quintals[item.order_id] += quantity_in_quintals(
            item.order_quantity,
            item.transport.quantity_unit,
        )

    unit_factors = {
        Order.QuantityUnit.MT: Decimal("10"),
        Order.QuantityUnit.QUINTAL: Decimal("1"),
        Order.QuantityUnit.KG: Decimal("0.01"),
    }
    for order in orders:
        if order.quantity_unit not in unit_factors:
            raise ValueError(f"Unsupported order quantity unit: {order.quantity_unit}")
        fulfilled = (
            fulfilled_in_quintals[order.id] / unit_factors[order.quantity_unit]
        ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        if order.quantity_fulfilled == fulfilled:
            continue
        order.quantity_fulfilled = fulfilled
        update_fields = ["quantity_fulfilled", "m_at"]
        if user is not None:
            order.m_by = user
            update_fields.append("m_by")
        order.save(update_fields=update_fields)


def transport_quantity_in_quintals(transport: Transport) -> Decimal:
    return quantity_in_quintals(
        transport.gross_wt,
        transport.quantity_unit,
    ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def sync_godown_transactions(
    transport: Transport,
    user,
    reverse_existing=False,
    record_current=True,
):
    if reverse_existing:
        transactions_to_reverse = GodownTransaction.objects.filter(
            transport=transport,
            transaction_type__in=[
                GodownTransaction.TransactionType.ENTRY,
                GodownTransaction.TransactionType.EXIT,
            ],
            reversals__isnull=True,
        ).select_related("godown", "commodity")

        for original in transactions_to_reverse:
            create_godown_transaction(
                transport=transport,
                godown=original.godown,
                commodity=original.commodity,
                quantity=original.quantity,
                transaction_type=GodownTransaction.TransactionType.REVERSAL,
                user=user,
                reversal_of=original,
            )

    if record_current:
        quantity = transport_quantity_in_quintals(transport)
        if transport.from_client_id:
            from_client = transport.from_client
            if from_client.type == BusinessClient.ClientType.MY_GODOWN:
                create_godown_transaction(
                    transport=transport,
                    godown=from_client,
                    commodity=transport.commodity,
                    quantity=quantity,
                    transaction_type=GodownTransaction.TransactionType.EXIT,
                    user=user,
                )

        if transport.to_client_id:
            to_client = transport.to_client
            if to_client.type == BusinessClient.ClientType.MY_GODOWN:
                create_godown_transaction(
                    transport=transport,
                    godown=to_client,
                    commodity=transport.commodity,
                    quantity=quantity,
                    transaction_type=GodownTransaction.TransactionType.ENTRY,
                    user=user,
                )


def create_godown_transaction(
    transport: Transport,
    godown: BusinessClient,
    commodity,
    quantity: Decimal,
    transaction_type: str,
    user,
    reversal_of: GodownTransaction | None = None,
):
    BusinessClient.objects.select_for_update().get(pk=godown.pk)
    latest_transaction = GodownTransaction.objects.filter(
        godown=godown,
        commodity=commodity,
    ).order_by("-id").first()
    balance = latest_transaction.remaining_quantity if latest_transaction else Decimal("0")

    if reversal_of is not None:
        balance_change = (
            -quantity
            if reversal_of.transaction_type == GodownTransaction.TransactionType.ENTRY
            else quantity
        )
    else:
        balance_change = (
            quantity
            if transaction_type == GodownTransaction.TransactionType.ENTRY
            else -quantity
        )

    GodownTransaction.objects.create(
        transport=transport,
        godown=godown,
        commodity=commodity,
        quantity=quantity,
        remaining_quantity=balance + balance_change,
        transaction_type=transaction_type,
        reversal_of=reversal_of,
        c_by=user,
    )


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
        values = transport_model_values(
            data.model_dump(exclude_unset=True, exclude={"items"})
        )
        values.setdefault("quantity_unit", "quintal")
        values.setdefault("rent_type", Transport.RentType.PER_UNIT)
        src_url = save_receipt(request, wt_rcpt_src, "src_rcpt")
        dst_url = save_receipt(request, wt_rcpt_dst, "dst_rcpt")
        if src_url is not None:
            values["wt_rcpt_src"] = src_url
        if dst_url is not None:
            values["wt_rcpt_dst"] = dst_url

        transport = Transport(**values, c_by=request.auth)
        transport.bulk_transport = None
        transport.full_clean()
        with transaction.atomic():
            transport.save()
            save_items(transport, data.items, request.auth)
            sync_godown_transactions(transport, request.auth)

        return {"success": True, "data": serialize_transport(transport)}
    except Exception as error:
        if settings.DEBUG:
            logger.exception("Transport request failed")
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
        update_godown_ledger = bool(
            {"commodity", "from_client", "to_client", "gross_wt", "gross_wt_unit"}
            & values.keys()
        )
        src_url = save_receipt(request, wt_rcpt_src, "src_rcpt")
        dst_url = save_receipt(request, wt_rcpt_dst, "dst_rcpt")
        if src_url is not None:
            values["wt_rcpt_src"] = src_url
        if dst_url is not None:
            values["wt_rcpt_dst"] = dst_url

        with transaction.atomic():
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

            if data.items is not None:
                save_items(transport, data.items, request.auth)
            else:
                recalculate_transport_order_fulfillment(
                    [transport.id],
                    request.auth,
                )

            if update_godown_ledger:
                sync_godown_transactions(transport, request.auth)

            transport = transport_queryset().get(id=transport.id)
        return {"success": True, "data": serialize_transport(transport)}
    except Exception as error:
        if settings.DEBUG:
            logger.exception("Transport request failed")
        return 400, {"success": False, "message": str(error)}


@router.get("/get/", response={200: TransportDetailResponseSchema})
def get_transport(request, data: Query[TransportGetDeleteSchema]):
    transport = get_object_or_404(
        transport_queryset(),
        id=data.id,
        is_active=True,
    )
    return {"success": True, "data": serialize_transport(transport)}


@router.delete("/del/", response={200: TransportDeleteResponseSchema})
@transaction.atomic
def delete_transport(request, data: TransportGetDeleteSchema):
    transport = get_object_or_404(Transport, id=data.id, is_active=True)
    affected_order_ids = active_order_ids_for_transports([transport.id])
    sync_godown_transactions(
        transport,
        request.auth,
        reverse_existing=True,
        record_current=False,
    )
    transport.is_active = False
    transport.d_by = request.auth
    transport.save(update_fields=["is_active", "d_by"])
    recalculate_order_fulfillment(affected_order_ids, request.auth)
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
    queryset = (
        transport_queryset()
        .prefetch_related(
            Prefetch(
                "billing_firm__profile_pictures",
                queryset=BusinessClientProfilePicture.objects.filter(
                    is_active=True,
                ).order_by("-id"),
                to_attr="active_profile_pictures",
            )
        )
        .filter(is_active=True, bulk_transport__isnull=True, **filters)
        .order_by("id")
    )
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
            "results": [
                serialize_transport(transport, include_billing_firm_image=True)
                for transport in transports
            ],
        },
    }


@router.post("/search/", response={200: TransportSearchResponseSchema})
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



@router.get("/clients/firms/sel/", response={200: dict})
def select_client_firms(request):
    clients = BusinessClient.objects.filter(
        is_active=True,
        type=BusinessClient.ClientType.MY_FIRM,
    ).order_by("name", "id").values("id", "name", "type", "city")
    return {"success": True, "data": list(clients)}


@router.get("/clients/locations/sel/", response={200: dict})
def select_client_locations(request):
    clients = BusinessClient.objects.filter(
        is_active=True,
    ).exclude(
        type=BusinessClient.ClientType.MY_FIRM,
    ).order_by("name", "id").values("id", "name", "type", "city")
    return {"success": True, "data": list(clients)}


def select_transport_orders(order_type):
    orders = Order.objects.filter(
        is_active=True,
        status__in=[Order.OrderStatus.PENDING, Order.OrderStatus.DRAFT],
        type=order_type,
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
                "rem_qty" : (order.quantity - order.quantity_fulfilled),
                "rem_qty_unit" : order.quantity_unit,
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


@router.get("/orders/po/sel/", response={200: dict})
def select_purchase_orders(request):
    return select_transport_orders(Order.OrderType.PURCHASE_ORDER)


@router.get("/orders/so/sel/", response={200: dict})
def select_sales_orders(request):
    return select_transport_orders(Order.OrderType.SALES_ORDER)


@router.get("/transporters/sel/", response={200: dict})
def select_transporters(request):
    transporters = Transporter.objects.filter(
        is_active=True,
    ).order_by("name", "id").values("id", "name", "agency", "city")
    return {"success": True, "data": list(transporters)}