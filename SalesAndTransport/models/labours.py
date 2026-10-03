from django.db import models

from StockPassCore.models import BaseModel


class Labour(BaseModel):
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
        db_table = "labour"
        verbose_name = "Labour"
        verbose_name_plural = "Labours"
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name