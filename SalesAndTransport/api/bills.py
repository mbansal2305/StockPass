from decimal import Decimal

from django.http import Http404
from ninja import Router, Schema

from SalesAndTransport.models import Transport
from StockPassCore.auth.permissions import OwnerAdminAuth


router = Router(auth=OwnerAdminAuth())


class BillTransportLookupSchema(Schema):
    billing_firm_id: int
    bill_no: str


class BillTransportResponseSchema(Schema):
    from_client: str | None
    to_client: str | None
    vehicle_no: str | None
    gross_wt: Decimal
    gross_wt_unit: str
    rent: Decimal
    billing_firm : str | None
    bill_no : str | None
    rent_type: str


@router.post("/search/", response={200: BillTransportResponseSchema})
def get_transport_by_bill(request, data: BillTransportLookupSchema):
    transport = (
        Transport.objects.filter(
            is_active=True,
            billing_firm_id=data.billing_firm_id,
            bill_no=data.bill_no,
        )
        .select_related("billing_firm", "from_client", "to_client")
        .order_by("id")
        .first()
    )
    if transport is None:
        raise Http404("Transport not found.")

    return {
        "from_client": transport.from_client.name if transport.from_client else None,
        "to_client": transport.to_client.name if transport.to_client else None,
        "vehicle_no": transport.vehicle_no,
        "gross_wt": transport.gross_wt,
        "gross_wt_unit": transport.quantity_unit,
        "billing_firm": transport.billing_firm.name,
        "bill_no" : transport.bill_no,
        "rent": transport.rent,
        "rent_type": transport.rent_type,
    }