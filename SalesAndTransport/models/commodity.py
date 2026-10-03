from django.db import models

from StockPassCore.models import BaseModel


class Commodity(BaseModel):
    name = models.CharField(
        max_length=32,
        db_index=True,
    )

    type = models.CharField(
            max_length=20,
            null=True,
            blank=True
        )

    bill_hammali = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    mandi_hammali = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    fill_qty = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=0,
    )

    class Meta:
        db_table = "commodity"
        verbose_name = "Commodity"
        verbose_name_plural = "Commodities"
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name