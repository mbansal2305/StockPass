import logging
import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router

from StockPassCore.auth.permissions import OwnerAdminAuth
from SalesAndTransport.models import BusinessClient, Commodity, GodownTransaction
from SalesAndTransport.schemas.godown import (
	GodownTransactionCreateSchema,
	GodownTransactionDeleteSchema,
	GodownTransactionListSchema,
	GodownTransactionUpdateSchema,
)


router = Router(auth=OwnerAdminAuth())
logger = logging.getLogger("ninja")


def quantity_in_quintals(quantity: Decimal, quantity_unit: str) -> Decimal:
	if quantity_unit == "mt":
		quantity *= Decimal("10")
	elif quantity_unit == "kg":
		quantity /= Decimal("100")
	return quantity.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def create_transaction_row(
	godown: BusinessClient,
	commodity: Commodity,
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
	balance = (
		latest_transaction.remaining_quantity
		if latest_transaction
		else Decimal("0")
	)

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

	return GodownTransaction.objects.create(
		godown=godown,
		commodity=commodity,
		quantity=quantity,
		remaining_quantity=balance + balance_change,
		transaction_type=transaction_type,
		reversal_of=reversal_of,
		c_by=user,
	)


def serialize_transaction(transaction_record: GodownTransaction):
	return {
		"id": transaction_record.id,
		"godown": transaction_record.godown_id,
		"commodity": transaction_record.commodity_id,
		"quantity": transaction_record.quantity,
		"quantity_unit": "quintal",
		"remaining_quantity": transaction_record.remaining_quantity,
		"transaction_type": transaction_record.transaction_type,
		"reversal_of": transaction_record.reversal_of_id,
	}


def serialize_stock_balance(stock_balance: dict):
	return {
		"godown": {
			"id": stock_balance["godown_id"],
			"name": stock_balance["godown__name"],
		},
		"commodity": {
			"id": stock_balance["commodity_id"],
			"name": stock_balance["commodity__name"],
		},
		"quantity": stock_balance["remaining_quantity"],
		"quantity_unit": "quintal",
	}


def get_transaction_date_range(time_range: str | None) -> tuple[date, date] | None:
	if not time_range:
		return None

	today = timezone.localdate()
	selection = time_range.strip().lower()
	if selection == "this_week":
		start_date = today - timedelta(days=today.weekday())
		return start_date, start_date + timedelta(days=6)
	if selection == "this_month":
		start_date = date(today.year, today.month, 1)
		end_date = date(
			today.year,
			today.month,
			calendar.monthrange(today.year, today.month)[1],
		)
		return start_date, end_date
	if selection == "last_three_months":
		month_index = today.year * 12 + today.month - 1 - 3
		year, month_index = divmod(month_index, 12)
		month = month_index + 1
		day = min(today.day, calendar.monthrange(year, month)[1])
		return date(year, month, day), today

	start_text, separator, end_text = time_range.partition("to")
	if not separator:
		raise ValueError("time_range must be a supported preset or YYYY-MM-DDtoYYYY-MM-DD.")
	try:
		start_date = date.fromisoformat(start_text.strip())
		end_date = date.fromisoformat(end_text.strip())
	except ValueError as error:
		raise ValueError(
			"time_range dates must use YYYY-MM-DD format."
		) from error
	if start_date > end_date:
		raise ValueError("time_range start date must be on or before end date.")
	return start_date, end_date


def get_manual_transaction(transaction_id: int):
	return get_object_or_404(
		GodownTransaction.objects.select_related("godown", "commodity"),
		id=transaction_id,
		transport__isnull=True,
		is_active=True,
		transaction_type__in=[
			GodownTransaction.TransactionType.ENTRY,
			GodownTransaction.TransactionType.EXIT,
		],
		reversals__isnull=True,
	)


def get_manual_references(godown_id: int, commodity_id: int):
	godown = get_object_or_404(
		BusinessClient,
		id=godown_id,
		is_active=True,
		type=BusinessClient.ClientType.MY_GODOWN,
	)
	commodity = get_object_or_404(Commodity, id=commodity_id, is_active=True)
	return godown, commodity


@router.post("/add/", response={200: dict, 400: dict})
@transaction.atomic
def add_godown_transaction(request, data: GodownTransactionCreateSchema):
	try:
		with transaction.atomic():
			godown, commodity = get_manual_references(data.godown, data.commodity)
			transaction_record = create_transaction_row(
				godown=godown,
				commodity=commodity,
				quantity=quantity_in_quintals(data.quantity, data.quantity_unit),
				transaction_type=GodownTransaction.TransactionType.ENTRY,
				user=request.auth,
			)
		return {"success": True, "data": serialize_transaction(transaction_record)}
	except Exception as error:
		if settings.DEBUG:
			logger.exception("Manual godown transaction request failed")
		return 400, {"success": False, "message": str(error)}


@router.patch("/upd/", response={200: dict, 400: dict})
@transaction.atomic
def update_godown_transaction(request, data: GodownTransactionUpdateSchema):
	try:
		with transaction.atomic():
			original = get_manual_transaction(data.id)
			godown, commodity = get_manual_references(data.godown, data.commodity)
			quantity = quantity_in_quintals(data.quantity, data.quantity_unit)

			create_transaction_row(
				godown=original.godown,
				commodity=original.commodity,
				quantity=original.quantity,
				transaction_type=GodownTransaction.TransactionType.REVERSAL,
				user=request.auth,
				reversal_of=original,
			)
			updated = create_transaction_row(
				godown=godown,
				commodity=commodity,
				quantity=quantity,
				transaction_type=original.transaction_type,
				user=request.auth,
			)
		return {"success": True, "data": serialize_transaction(updated)}
	except Exception as error:
		if settings.DEBUG:
			logger.exception("Manual godown transaction request failed")
		return 400, {"success": False, "message": str(error)}


@router.delete("/del/", response={200: dict, 400: dict})
@transaction.atomic
def delete_godown_transaction(request, data: GodownTransactionDeleteSchema):
	try:
		with transaction.atomic():
			original = get_manual_transaction(data.id)
			reversal = create_transaction_row(
				godown=original.godown,
				commodity=original.commodity,
				quantity=original.quantity,
				transaction_type=GodownTransaction.TransactionType.REVERSAL,
				user=request.auth,
				reversal_of=original,
			)
		return {"success": True, "id": original.id, "reversal_id": reversal.id}
	except Exception as error:
		if settings.DEBUG:
			logger.exception("Manual godown transaction request failed")
		return 400, {"success": False, "message": str(error)}


@router.post("/lst/", response={200: dict, 400: dict})
def list_godown_transactions(request, data: GodownTransactionListSchema):
	if data.page < 1 or data.page_size < 1 or data.page_size > 100:
		return 400, {"success": False, "message": "Invalid pagination values."}
	try:
		date_range = get_transaction_date_range(data.time_range)
	except ValueError as error:
		return 400, {"success": False, "message": str(error)}

	filters: dict[str, int | bool] = {"is_active": True}
	if data.godown is not None:
		filters["godown_id"] = data.godown
	if data.commodity is not None:
		filters["commodity_id"] = data.commodity

	stock_queryset = GodownTransaction.objects.filter(**filters)
	stock_balances = stock_queryset.order_by().values(
		"godown_id",
		"godown__name",
		"commodity_id",
		"commodity__name",
	).distinct().annotate(
		remaining_quantity=Subquery(
			GodownTransaction.objects.filter(
				is_active=True,
				godown_id=OuterRef("godown_id"),
				commodity_id=OuterRef("commodity_id"),
			).order_by("-id").values("remaining_quantity")[:1]
		)
	).order_by("godown__name", "commodity__name")

	transaction_queryset = GodownTransaction.objects.filter(**filters)
	if data.transaction_type is not None:
		transaction_queryset = transaction_queryset.filter(
			transaction_type=data.transaction_type,
		)
	if date_range is not None:
		transaction_queryset = transaction_queryset.filter(
			c_at__date__range=date_range,
		)
	transaction_queryset = transaction_queryset.select_related(
			"godown",
			"commodity",
		).order_by("-id")
	total = transaction_queryset.count()
	start = (data.page - 1) * data.page_size
	transactions = transaction_queryset[start : start + data.page_size]

	return {
		"success": True,
		"data": {
			"page": data.page,
			"page_size": data.page_size,
			"total": total,
			"total_pages": (total + data.page_size - 1) // data.page_size,
			"results": [serialize_transaction(item) for item in transactions],
			"total_stock": [
				serialize_stock_balance(balance)
				for balance in stock_balances
			],
		},
	}
