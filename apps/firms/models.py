from django.db import models
import uuid

class Firm(models.Model):
    """
    Represents a tenant (customer/company) in the system.
    Every user, document, chunk and search belongs to exactly one Firm.
    """

    id= models.UUIDField(
        primary_key=True, 
        default=uuid.uuid7, 
        editable=False
        )
    name= models.CharField(
        max_length=255
        )

    created_at= models.DateTimeField(
        auto_now_add=True
        )

    def __str__(self):
        return self.name