from django.db import models

from StockPassCore.models import BaseModel


class BusinessClient(BaseModel):

    class ClientType(models.TextChoices):
        OTHER_GODOWN = "other_godown"
        COMPANY = "company"
        LOCATION = "location"
        MY_GODOWN = "my_godown"
        MY_FIRM = "my_firm"

    class ClientFlag(models.TextChoices):
        GOOD = "good"
        BAD = "bad"
        BLACKLISTED = "blacklisted"
        FRAUD = "fraud"
        UNREASONABLE_CLAIMS = "unreasonable_claims"
        NEUTRAL = "neutral"

    name = models.CharField(
        max_length=100,
        db_index=True,
    )

    address = models.TextField(
        blank=True,
        null=True,
    )

    city = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        db_index=True,
    )

    pincode = models.CharField(
        max_length=8,
        blank=True,
        null=True,
        db_index=True,
    )

    type = models.CharField(
        max_length=30,
        choices=ClientType.choices,
        db_index=True,
    )

    flag = models.CharField(
        max_length=30,
        choices=ClientFlag.choices,
        blank=True,
        null=True,
        db_index=True,
    )

    location_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
    )


    class Meta:
        db_table = "business_client"
        verbose_name = "Business Client"
        verbose_name_plural = "Business Clients"
        indexes = [
            models.Index(fields=["name", "type"]),
            models.Index(fields=["city", "type"]),
            models.Index(fields=["flag", "is_active"]),
        ]

    def __str__(self):
        return self.name