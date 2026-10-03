from django.db import models

from StockPassCore.models import BaseModel


class Tempo(BaseModel):
    name = models.CharField(
        max_length=50,
        db_index=True,
    )

    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
    )

    class Meta:
        db_table = "tempo"
        verbose_name = "Tempo"
        verbose_name_plural = "Tempos"
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name