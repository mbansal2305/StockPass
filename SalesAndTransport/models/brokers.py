from django.db import models

from StockPassCore.models import BaseModel


class Broker(BaseModel):
    name = models.CharField(
        max_length=255,
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