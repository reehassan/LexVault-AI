# apps/search/tests/test_search_service.py

import pytest

from apps.documents.models import Chunk, Document
from apps.firms.models import Firm
from apps.search.services.search import (
    InvalidSearchQueryError,
    search_documents,
)


@pytest.fixture
def firm(db):
    return Firm.objects.create(name="Test Firm")


@pytest.fixture
def user(firm):
    from django.contrib.auth import get_user_model

    User = get_user_model()

    return User.objects.create_user(
        username="search_user",
        firm=firm,
        password="password",
    )


@pytest.fixture
def document(firm, user):
    return Document.objects.create(
        firm=firm,
        uploaded_by=user,
        filename="contract.pdf",
        file_size_bytes=100,
        storage_path="firms/test/contract.pdf",
        status=Document.ProcessingStatus.READY,
    )


def make_vector(x, y=0.0, dim=384):
    vector = [0.0] * dim
    vector[0] = x
    vector[1] = y
    return vector


@pytest.mark.django_db
def test_search_documents_returns_results(
    firm,
    document,
    monkeypatch,
):
    query_embedding = make_vector(1, 0)

    monkeypatch.setattr(
        "apps.search.services.search.embed_query",
        lambda query: query_embedding,
    )

    Chunk.objects.create(
        document=document,
        firm=firm,
        page_number=2,
        chunk_index=0,
        content="Termination clause content.",
        token_count=4,
        embedding=make_vector(1, 0),
    )

    results = search_documents(
        query="What are the termination clauses?",
        firm_id=firm.id,
    )

    assert len(results) == 1
    assert results[0]["document_filename"] == "contract.pdf"
    assert results[0]["page_number"] == 2
    assert results[0]["content"] == "Termination clause content."
    assert "similarity" in results[0]


@pytest.mark.django_db
def test_search_documents_empty_vault_returns_empty(
    firm,
    monkeypatch,
):
    monkeypatch.setattr(
        "apps.search.services.search.embed_query",
        lambda query: make_vector(1, 0),
    )

    results = search_documents(
        query="What are the payment terms?",
        firm_id=firm.id,
    )

    assert results == []


@pytest.mark.django_db
def test_search_documents_never_crosses_firms(
    firm,
    document,
    monkeypatch,
):
    other_firm = Firm.objects.create(
        name="Other Firm"
    )

    from django.contrib.auth import get_user_model

    User = get_user_model()

    other_user = User.objects.create_user(
        username="other_user",
        firm=other_firm,
        password="password",
    )

    other_document = Document.objects.create(
        firm=other_firm,
        uploaded_by=other_user,
        filename="secret.pdf",
        file_size_bytes=100,
        storage_path="firms/other/secret.pdf",
        status=Document.ProcessingStatus.READY,
    )

    Chunk.objects.create(
        document=document,
        firm=firm,
        page_number=1,
        chunk_index=0,
        content="Firm A content.",
        token_count=3,
        embedding=make_vector(1, 0),
    )

    Chunk.objects.create(
        document=other_document,
        firm=other_firm,
        page_number=1,
        chunk_index=0,
        content="Firm B secret content.",
        token_count=4,
        embedding=make_vector(1, 0),
    )

    monkeypatch.setattr(
        "apps.search.services.search.embed_query",
        lambda query: make_vector(1, 0),
    )

    results = search_documents(
        query="Find relevant content.",
        firm_id=firm.id,
    )

    assert len(results) == 1
    assert results[0]["document_filename"] == "contract.pdf"
    assert results[0]["content"] == "Firm A content."


def test_search_documents_rejects_empty_query():
    with pytest.raises(InvalidSearchQueryError):
        search_documents(
            query="",
            firm_id="firm-id",
        )


def test_search_documents_rejects_whitespace_query():
    with pytest.raises(InvalidSearchQueryError):
        search_documents(
            query="   ",
            firm_id="firm-id",
        )


def test_search_documents_rejects_non_string_query():
    with pytest.raises(InvalidSearchQueryError):
        search_documents(
            query=None,
            firm_id="firm-id",
        )