from django.db import models
from StockPassCore.models import BaseModel
from .order import Order
from .commodity import Commodity
from .clients import BusinessClient


class Transporter(BaseModel):
    name = models.CharField(
        max_length=255,
        db_index=True,
    )

    class Meta:
        db_table = "transporter"
        verbose_name = "Transporter"
        verbose_name_plural = "Transporters"
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name


class Transport(BaseModel):

    class TransportStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERY = "delivery", "Delivery"
        FINANCE = "finance", "Finance"
        PAID = "paid", "Paid"

    billing_firm = models.ForeignKey(
        BusinessClient,
        related_name="transports_billed",
        on_delete=models.PROTECT,
    )

    bill_no = models.CharField(
        max_length=10,
        db_index=True,
    )

    commodity = models.ForeignKey(
        Commodity,
        related_name="transports",
        on_delete=models.PROTECT,
    )

    from_client = models.ForeignKey(
        BusinessClient,
        related_name="transports_from",
        on_delete=models.PROTECT,
    )

    to_client = models.ForeignKey(
        BusinessClient,
        related_name="transports_to",
        on_delete=models.PROTECT,
    )

    gross_wt = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=0,
    )

    bag_nos = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
    )

    bag_wt = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=0,
    )

    vehicle_no = models.CharField(
        max_length=12,
        db_index=True,
    )

    transporter = models.ForeignKey(
        Transporter,
        related_name="transports",
        on_delete=models.PROTECT,
    )

    anugya = models.BooleanField(
        default=False,
    )

    gatepass = models.BooleanField(
        default=False,
    )

    unload_date = models.DateField(
        null=True,
        blank=True,
    )

    rcvd_wt = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=0,
    )

    rent = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    adv_by_client = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    adv_by_firm = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    final_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    status = models.CharField(
        max_length=20,
        choices=TransportStatus.choices,
        default=TransportStatus.PENDING,
        db_index=True,
    )

    wt_rcpt_src = models.ImageField(
        upload_to="transport/weight_receipts/source/",
        null=True,
        blank=True,
    )

    wt_rcpt_dst = models.ImageField(
        upload_to="transport/weight_receipts/destination/",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "transport"
        verbose_name = "Transport"
        verbose_name_plural = "Transports"
        indexes = [
            models.Index(fields=["bill_no"]),
            models.Index(fields=["vehicle_no"]),
            models.Index(fields=["status"]),
            models.Index(fields=["billing_firm", "status"]),
            models.Index(fields=["from_client", "status"]),
            models.Index(fields=["to_client", "status"]),
            models.Index(fields=["commodity", "status"]),
            models.Index(fields=["transporter", "status"]),
            models.Index(fields=["unload_date"]),
        ]

    def __str__(self):
        return self.bill_no


class TransportItems(BaseModel):

    transport = models.ForeignKey(
        Transport,
        related_name="items",
        on_delete=models.CASCADE,
    )

    order = models.ForeignKey(
        Order,
        related_name="transport_items",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=0,
    )

    class Meta:
        db_table = "transport_items"
        verbose_name = "Transport Item"
        verbose_name_plural = "Transport Items"
        indexes = [
            models.Index(fields=["transport"]),
            models.Index(fields=["order"]),
        ]

    def __str__(self):
        return f"{self.transport.bill_no} - {self.quantity}"