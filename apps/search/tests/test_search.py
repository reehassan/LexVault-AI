# apps/search/tests/test_search.py
"""
Tests for retrieve_chunks() — vector similarity search.

Uses hand-constructed embeddings with known, unambiguous cosine
similarities rather than real embedded text, specifically to avoid a
test that passes by semantic luck rather than provable ordering.
"""

import pytest

from django.contrib.auth import get_user_model

from apps.documents.models import Chunk, Document
from apps.search.services.retriever import retrieve_chunks
from apps.firms.models import Firm


User = get_user_model()


def make_vector(x, y=0.0, dim=384):
    """
    Builds deterministic vectors for cosine similarity testing.

    Uses direction differences, not magnitude differences, because
    cosine similarity ignores vector length.

    Examples:
        [1,0]     -> identical direction
        [0.707,0.707] -> medium similarity
        [-1,0]    -> opposite direction
    """
    vector = [0.0] * dim
    vector[0] = x
    vector[1] = y
    return vector


@pytest.fixture
def firm(db):
    return Firm.objects.create(name="Test Firm")


@pytest.fixture
def user(firm):
    return User.objects.create_user(
        username="uploader",
        firm=firm,
        password="x",
    )


@pytest.fixture
def document(firm, user):
    return Document.objects.create(
        firm=firm,
        uploaded_by=user,
        filename="test.pdf",
        file_size_bytes=100,
        storage_path="firms/test/test.pdf",
        status=Document.ProcessingStatus.READY,
    )


@pytest.mark.django_db
def test_retrieve_chunks_orders_by_similarity_descending(firm, document):
    """
    Verify chunks are returned from highest cosine similarity
    to lowest cosine similarity.
    """

    closest = Chunk.objects.create(
        document=document,
        firm=firm,
        page_number=1,
        chunk_index=0,
        content="closest match",
        token_count=2,
        embedding=make_vector(1, 0),
    )

    middle = Chunk.objects.create(
        document=document,
        firm=firm,
        page_number=1,
        chunk_index=1,
        content="middle match",
        token_count=2,
        embedding=make_vector(0.707, 0.707),
    )

    farthest = Chunk.objects.create(
        document=document,
        firm=firm,
        page_number=1,
        chunk_index=2,
        content="farthest match",
        token_count=2,
        embedding=make_vector(-1, 0),
    )

    query_vector = make_vector(1, 0)

    results = retrieve_chunks(
        query_vector,
        firm.id,
        top_k=3,
    )

    result_ids_in_order = [
        result["chunk_id"]
        for result in results
    ]

    assert result_ids_in_order == [
        closest.id,
        middle.id,
        farthest.id,
    ]

    similarities = [
        result["similarity"]
        for result in results
    ]

    assert similarities == sorted(
        similarities,
        reverse=True,
    )


@pytest.mark.django_db
def test_retrieve_chunks_never_crosses_firms(firm, document):

    firm_b = Firm.objects.create(name="Firm B")

    user_b = User.objects.create_user(
        username="uploader_b",
        firm=firm_b,
        password="x",
    )

    document_b = Document.objects.create(
        firm=firm_b,
        uploaded_by=user_b,
        filename="other.pdf",
        file_size_bytes=100,
        storage_path="firms/other/other.pdf",
        status=Document.ProcessingStatus.READY,
    )

    Chunk.objects.create(
        document=document,
        firm=firm,
        page_number=1,
        chunk_index=0,
        content="firm A content",
        token_count=2,
        embedding=make_vector(1, 0),
    )

    Chunk.objects.create(
        document=document_b,
        firm=firm_b,
        page_number=1,
        chunk_index=0,
        content="firm B content",
        token_count=2,
        embedding=make_vector(1, 0),
    )

    results = retrieve_chunks(
        make_vector(1, 0),
        firm.id,
        top_k=5,
    )

    assert len(results) == 1

    assert results[0]["document_filename"] == "test.pdf"

    assert all(
        result["document_filename"] != "other.pdf"
        for result in results
    )


@pytest.mark.django_db
def test_retrieve_chunks_empty_vault_returns_empty_list(firm):

    results = retrieve_chunks(
        make_vector(1, 0),
        firm.id,
        top_k=5,
    )

    assert results == []


@pytest.mark.django_db
def test_retrieve_chunks_respects_top_k_limit(firm, document):

    for i in range(8):
        Chunk.objects.create(
            document=document,
            firm=firm,
            page_number=1,
            chunk_index=i,
            content=f"chunk {i}",
            token_count=2,
            embedding=make_vector(
                1,
                float(i),
            ),
        )

    results = retrieve_chunks(
        make_vector(1, 0),
        firm.id,
        top_k=3,
    )

    assert len(results) == 3