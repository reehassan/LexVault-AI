import uuid

from django.db import models


class SearchQuery(models.Model):
    class ResultType(models.TextChoices):
        FOUND = "found", "Found"
        NOT_FOUND = "not_found", "Not Found"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid7,
        editable=False,
    )

    firm = models.ForeignKey(
        "firms.Firm",
        on_delete=models.CASCADE,
        related_name="search_queries",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="search_queries",
    )
    query_text = models.TextField()

    result_type = models.CharField(
        max_length=10,
        choices=ResultType.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Query by {self.user.username}: {self.query_text[:50]}"

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(query_text__gt=""),
                name="query_text_not_empty",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "-created_at"],
                name="idx_searchquery_user_created",
            ),
        ]


class Citation(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid7,
        editable=False,
    )
    search_query = models.ForeignKey(
        "search.SearchQuery",
        on_delete=models.CASCADE,
        related_name="citations",
    )
    chunk = models.ForeignKey(
        "documents.Chunk",
        on_delete=models.CASCADE,
        related_name="citations",
    )
    relevance_score = models.FloatField()
    rank = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Citation rank {self.rank} for {self.search_query_id}"

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(relevance_score__gte=0) & models.Q(relevance_score__lte=1),
                name="relevance_score_between_0_and_1",
            ),
            
            models.CheckConstraint(
                condition=models.Q(rank__gte=1),
                name="rank_at_least_1",
            ),
            models.UniqueConstraint(
                fields=["search_query", "chunk"],
                name="unique_chunk_per_search_query",
            ),
            models.UniqueConstraint(
                fields=["search_query", "rank"],
                name="unique_rank_per_search_query",
            ),
        ]
        indexes = [
            models.Index(fields=["search_query"], name="idx_citation_query"),
            models.Index(fields=["chunk"], name="idx_citation_chunk"),
        ]