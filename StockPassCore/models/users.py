from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group
from django.db import models
from django.utils import timezone
from django.conf import settings



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


    profile_picture = models.URLField(max_length=500, blank=True, null=True)
    last_login = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=False)
    gender_code = models.CharField(max_length=5, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)


    def save(self, *args, **kwargs):
        self.username = self.email
        if not self.pk:
            self.last_login = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"
