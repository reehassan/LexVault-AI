import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Custom authentication model.

    Extends Django's built-in User while adding
    tenant (Firm) ownership.
    """

    id= models.UUIDField(
        primary_key=True, 
        default=uuid.uuid7, 
        editable=False
        )
    username = models.CharField(
        max_length=150,
        unique=False,
        db_index=True,
    )

    firm= models.ForeignKey(
        "firms.Firm",
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )

    created_at= models.DateTimeField(
        auto_now_add=True
        )

    def __str__(self):
        return f"{self.username} ({self.firm})"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["firm","username"],
                name="unique_username_per_firm",
                ),
        ]

        indexes = [
            models.Index(
                fields=["firm"],
                name="idx_user_firm",
            ),
        ]

