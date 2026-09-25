from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        ADMIN = "ADMIN", "Admin"
        ACCOUNTANT = "ACCOUNTANT", "Accountant"
        LABOUR = "LABOUR", "Labour"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.LABOUR,
    )

    profile_picture = models.URLField(
        max_length=500,
        blank=True,
        null=True,
    )

    is_active = models.BooleanField(default=True)

    gender_code = models.CharField(
        max_length=5,
        blank=True,
        null=True,
    )

    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"