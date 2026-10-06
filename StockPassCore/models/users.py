from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", self.model.Role.OWNER)
        return super().create_superuser(
            username,
            email=email,
            password=password,
            **extra_fields,
        )


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

    objects = UserManager()

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