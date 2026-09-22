
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from StockPassCore.models.users import User
import re
from django.core.exceptions import ValidationError


class BaseModel(models.Model):
    is_active = models.BooleanField(default=True)
    c_by = models.ForeignKey(
        User,
        related_name="%(class)s_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    c_at = models.DateTimeField(auto_now_add=True)

    m_by = models.ForeignKey(
        User,
        related_name="%(class)s_updated",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    m_at = models.DateTimeField(auto_now=True)
    d_at = models.DateTimeField(null=True, blank=True)
    d_by = models.ForeignKey(
        User,
        related_name="%(class)s_deleted",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True

    @property
    def full_c_by_name(self):
        if self.c_by:
            return f"{self.c_by.first_name} {self.c_by.last_name}"
        return None

    @property
    def full_m_by_name(self):
        if self.m_by:
            return f"{self.m_by.first_name} {self.m_by.last_name}"
        return None

    @property
    def full_d_by_name(self):
        if self.d_by:
            return f"{self.d_by.first_name} {self.d_by.last_name}"
        return None
