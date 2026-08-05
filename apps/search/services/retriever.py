# apps/search/services/retriever.py
"""
Vector similarity search over Chunk embeddings.

Pure-ish service — takes a Django queryset (real DB access, unlike
extractor/chunker/embedder which are fully pure), but keeps all
business logic in one place: tenant filtering happens before the
distance computation so Postgres can use the (firm, document) index
to shrink the candidate set before the more expensive vector distance
math runs, rather than computing distance across the whole table.
"""
from pgvector.django import CosineDistance

from apps.documents.models import Chunk


def retrieve_chunks(query_embedding, firm_id, top_k=5):
    """
    Find the top_k chunks most similar to query_embedding, scoped to
    one firm.

    Args:
        query_embedding (list[float]): 384-dim vector, same shape as
            Chunk.embedding (a plain Python list — confirmed via
            Chunk.objects.first().embedding returning `list`, not a
            numpy array).
        firm_id (UUID): tenant scope. Filtering happens BEFORE the
            distance computation, not after — this lets Postgres use
            idx_chunk_firm_document to shrink the candidate set first,
            rather than computing distance across every chunk in the
            table and discarding most of it.
        top_k (int): max number of results to return.

    Returns:
        list[dict]: each dict has:
            - chunk_id
            - document_id
            - document_filename
            - page_number
            - content
            - similarity (float, 0-1, HIGHER = more similar —
              this is 1 - cosine_distance, converted here because
              pgvector's CosineDistance gives distance, not
              similarity, and nothing about that native output is
              obvious from its name alone)
    """
    results = (
        Chunk.objects
        .filter(firm_id=firm_id)
        .select_related("document")
        .annotate(distance=CosineDistance("embedding", query_embedding))
        .order_by("distance")[:top_k]
    )

    return [
        {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "document_filename": chunk.document.filename,
            "page_number": chunk.page_number,
            "content": chunk.content,
            "similarity": 1 - chunk.distance,
        }
        for chunk in results
    ]