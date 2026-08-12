# apps/search/services/search.py

"""
Application-level semantic search service.

Pipeline:

    User question
        ↓
    Query embedding
        ↓
    Tenant-scoped vector retrieval
        ↓
    Top-k relevant chunks

This service coordinates the embedding and retrieval layers.
It does not perform vector math itself.
"""

from apps.documents.services.embedder import embed_query
from apps.search.services.retriever import retrieve_chunks


class InvalidSearchQueryError(ValueError):
    """Raised when a search question is invalid."""

    pass


def search_documents(question, firm_id, top_k=5):
    """
    Search documents belonging to one firm.

    Args:
        question (str): user's natural-language search question.
        firm_id: authenticated user's firm ID.
        top_k (int): maximum number of chunks to return.

    Returns:
        list[dict]: relevant chunks with:
            - chunk_id
            - document_id
            - document_filename
            - page_number
            - content
            - similarity

    Raises:
        InvalidSearchQueryError: if question is empty or invalid.
    """
    if not isinstance(question, str):
        raise InvalidSearchQueryError(
            "question must be a string"
        )

    if not question.strip():
        raise InvalidSearchQueryError(
            "question must be a non-empty string"
        )

    query_embedding = embed_query(question)

    return retrieve_chunks(
        query_embedding=query_embedding,
        firm_id=firm_id,
        top_k=top_k,
    )