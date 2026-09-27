from datetime import date, timedelta

from django.db.models import Count
from django.utils import timezone
from ninja import Router

from StockPassCore.auth.permissions import OwnerAdminAuth
from SalesAndTransport.models import Order, Transport
from SalesAndTransport.schemas.dashboard import (
	DashboardRequestSchema,
	DashboardResponseSchema,
	TimeRange,
)


router = Router(auth=OwnerAdminAuth())


def get_range_start(time_range: TimeRange, today: date) -> date | None:
	if time_range == "this_month":
		return today.replace(day=1)
	if time_range == "this_week":
		return today - timedelta(days=today.weekday())
	return None


def apply_time_range(queryset, time_range: TimeRange, today: date):
	range_start = get_range_start(time_range, today)
	if range_start is None:
		return queryset
	return queryset.filter(c_at__date__gte=range_start)


@router.post("/", response=DashboardResponseSchema)
def get_dashboard(request, data: DashboardRequestSchema):
	time_range = data.time_range
	today = timezone.localdate()
	pending_orders = apply_time_range(
		Order.objects.filter(is_active=True, status=Order.OrderStatus.PENDING),
		time_range,
		today,
	)
	draft_orders = apply_time_range(
		Order.objects.filter(is_active=True, status=Order.OrderStatus.DRAFT),
		time_range,
		today,
	)
	expiring_orders = pending_orders.filter(
		expiry_date__isnull=False,
	).select_related(
		"from_client",
		"to_client",
		"commodity",
	).order_by("expiry_date", "id")[:10]

	active_transports = apply_time_range(
		Transport.objects.filter(is_active=True),
		time_range,
		today,
	)
	in_transit_statuses = [
		Transport.TransportStatus.PENDING,
		Transport.TransportStatus.DELIVERY,
		Transport.TransportStatus.FINANCE,
	]
	in_transit = active_transports.filter(status__in=in_transit_statuses)
	status_counts = {
		status: 0 for status, _label in Transport.TransportStatus.choices
	}
	status_counts.update({
		row["status"]: row["count"]
		for row in active_transports.values("status").annotate(count=Count("id"))
	})

	return {
		"success": True,
		"data": {
			"time_range": time_range,
			"pending_orders_count": pending_orders.count(),
			"draft_orders_count": draft_orders.count(),
			"expiring_orders": [
				{
					"id": order.id,
					"order_no": order.order_no,
					"type": order.type,
					"expiry_date": order.expiry_date,
					"days_until_expiry": (order.expiry_date - today).days,
					"quantity": order.quantity,
					"quantity_unit": order.quantity_unit,
					"quantity_fulfilled": order.quantity_fulfilled,
					"from_client": order.from_client.name if order.from_client else None,
					"to_client": order.to_client.name if order.to_client else None,
					"commodity": order.commodity.name,
				}
				for order in expiring_orders
			],
			"in_transit_count": in_transit.count(),
			"transport_status_counts": status_counts,
			"in_transit_transports": [
				{
					"id": transport.id,
					"vehicle_no": transport.vehicle_no,
					"bill_no": transport.bill_no,
					"status": transport.status,
					"gross_wt": transport.gross_wt,
					"quantity_unit": transport.quantity_unit,
					"unload_date": transport.unload_date,
				}
				for transport in in_transit.order_by("c_at", "id")
			],
		},
	}
