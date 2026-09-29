from django.db import models

from StockPassCore.models import BaseModel

from .transport import Transport
from .commodity import Commodity
from .clients import  BusinessClient


class GodownTransaction(BaseModel):

    class TransactionType(models.TextChoices):
        ENTRY = "entry", "Entry"
        EXIT = "exit", "Exit"
        REVERSAL = "reversal", "Reversal"

    godown = models.ForeignKey(
        BusinessClient,
        related_name="godown_transactions",
        on_delete=models.PROTECT,
    )

    commodity = models.ForeignKey(
        Commodity,
        related_name="godown_transactions",
        on_delete=models.PROTECT,
    )

    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=0,
    )

    remaining_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=0,
    )

    transport = models.ForeignKey(
        Transport,
        related_name="godown_transactions",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    transaction_type = models.CharField(
        max_length=10,
        choices=TransactionType.choices,
    )

    reversal_of = models.ForeignKey(
        "self",
        related_name="reversals",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "godown_transaction"
        verbose_name = "Godown Transaction"
        verbose_name_plural = "Godown Transactions"

        indexes = [
            # Used for finding transactions/history
            models.Index(
                fields=["godown", "commodity"]
            ),

            # Used for finding the latest balance quickly
            models.Index(
                fields=["godown", "commodity", "-id"]
            ),

            # Used when fetching transactions for a transport
            models.Index(
                fields=["transport"]
            ),

            models.Index(
                fields=["transaction_type"]
            ),

            models.Index(
                fields=["reversal_of"]
            ),
        ]

    def __str__(self):
        return (
            f"{self.godown.name} - "
            f"{self.commodity.name} - "
            f"{self.quantity} "
            f"(Balance: {self.remaining_quantity})"
        )