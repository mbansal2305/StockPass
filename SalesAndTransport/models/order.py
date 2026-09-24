from django.db import models
from StockPassCore.models import BaseModel

from .brokers import Broker
from .commodity import Commodity
from .clients import BusinessClient


class Order(BaseModel):

    class OrderType(models.TextChoices):
        SALES_ORDER = "sales_order"
        PURCHASE_ORDER = "purchase_order"

    class OrderStatus(models.TextChoices):
        PENDING = "pending"
        COMPLETED = "completed"

    type = models.CharField(
        max_length=20,
        choices=OrderType.choices,
        db_index=True,
    )

    order_no = models.CharField(
        max_length=10,
        db_index=True,
    )

    from_client = models.ForeignKey(
        BusinessClient,
        related_name="orders_from",
        on_delete=models.PROTECT,
        
    )

    to_client = models.ForeignKey(
        BusinessClient,
        related_name="orders_to",
        on_delete=models.PROTECT,
    )

    commodity = models.ForeignKey(
        Commodity,
        related_name="orders",
        on_delete=models.PROTECT,
    )

    rate = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=0,
    )

    start_date = models.DateField(
        null=True,
        blank=True,
    )

    expiry_date = models.DateField(
        null=True,
        blank=True,
    )

    quantity_fulfilled = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=0,
    )

    broker = models.ForeignKey(
        Broker,
        related_name="orders",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )

    notes = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "order"
        verbose_name = "Order"
        verbose_name_plural = "Orders"

        indexes = [
            models.Index(fields=["order_no"]),
            models.Index(fields=["type", "status"]),
            models.Index(fields=["from_client", "status"]),
            models.Index(fields=["to_client", "status"]),
            models.Index(fields=["commodity", "status"]),
            models.Index(fields=["broker", "status"]),
        ]

    def __str__(self):
        return self.order_no