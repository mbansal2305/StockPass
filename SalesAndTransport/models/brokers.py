from django.db import models

from StockPassCore.models import BaseModel


class Broker(BaseModel):
    name = models.CharField(
        max_length=255,
        db_index=True,
    )

    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
    )

    

    class Meta:
        db_table = "broker"
        verbose_name = "Broker"
        verbose_name_plural = "Brokers"
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name