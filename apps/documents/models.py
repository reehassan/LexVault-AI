import uuid
from django.db import models
from pgvector.django import VectorField, HnswIndex


class Document(models.Model):
    class ProcessingStatus(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid7,
        editable=False,
    )
    firm = models.ForeignKey(
        "firms.Firm",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    uploaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="uploaded_documents",
    )
    filename = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.UPLOADED,
    )
    page_count = models.IntegerField(null=True, blank=True)
    file_size_bytes = models.BigIntegerField()
    storage_path = models.CharField(max_length=500)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.filename} ({self.firm})"

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(page_count__gte=0),
                name="page_count_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(file_size_bytes__gt=0),
                name="file_size_bytes_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["firm"], name="idx_document_firm"),
            models.Index(fields=["firm", "status"], name="idx_document_firm_status"),
        ]


class Chunk(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid7,
        editable=False
    )

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="chunks",
    )

    firm = models.ForeignKey(
        "firms.Firm",
        on_delete=models.CASCADE,
        related_name="chunks",
    )

    page_number = models.PositiveIntegerField()
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    token_count = models.PositiveIntegerField()
    embedding = VectorField(dimensions=384)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.filename}"

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(page_number__gt=0),
                name="page_number_positive",
            ),

            models.CheckConstraint(
                condition=models.Q(chunk_index__gte=0),
                name="chunk_index_non_negative",
            ),

            models.CheckConstraint(
                condition=~models.Q(content=""),
                name="content_not_empty",
            ),

            models.CheckConstraint(
                condition=models.Q(token_count__gt=0),
                name="token_count_positive",
            ),

            models.UniqueConstraint(
                fields=["document", "chunk_index"],
                name="unique_chunk_index_per_document",
            ),


        ]
        indexes = [
            models.Index(fields=["firm", "document"], name="idx_chunk_firm_document"),
            HnswIndex(
                name="idx_chunk_embedding",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

