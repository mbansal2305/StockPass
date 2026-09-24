from django.db import models

from StockPassCore.models import BaseModel


class Commodity(BaseModel):
    name = models.CharField(
        max_length=255,
        db_index=True,
    )

    type = models.CharField(
            max_length=255,
            null=True,
            blank=True
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