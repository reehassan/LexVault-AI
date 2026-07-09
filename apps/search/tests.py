import pytest
from django.db import IntegrityError

from apps.firms.models import Firm
from apps.documents.models import Document, Chunk
from apps.search.models import SearchQuery, Citation
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def firm(db):
    return Firm.objects.create(name="Test Firm")


@pytest.fixture
def user(firm):
    return User.objects.create_user(username="uploader", firm=firm, password="x")


@pytest.fixture
def document(firm, user):
    return Document.objects.create(
        firm=firm,
        uploaded_by=user,
        filename="contract.pdf",
        file_size_bytes=1024,
        storage_path="/documents/contract.pdf",
    )


@pytest.fixture
def chunk(firm, document):
    return Chunk.objects.create(
        document=document,
        firm=firm,
        page_number=1,
        chunk_index=0,
        content="This clause governs indemnification.",
        token_count=8,
        embedding=[0.1] * 384,
    )


# ---------- SearchQuery tests ----------

@pytest.mark.django_db
def test_search_query_creation_found(firm, user):
    query = SearchQuery.objects.create(
        firm=firm,
        user=user,
        query_text="What does the indemnification clause say?",
        result_type=SearchQuery.ResultType.FOUND,
    )
    assert query.result_type == "found"


@pytest.mark.django_db
def test_search_query_text_cannot_be_empty(firm, user):
    with pytest.raises(IntegrityError):
        SearchQuery.objects.create(
            firm=firm,
            user=user,
            query_text="",
            result_type=SearchQuery.ResultType.NOT_FOUND,
        )


@pytest.mark.django_db
def test_search_query_deleted_when_user_deleted(firm, user):
    query = SearchQuery.objects.create(
        firm=firm,
        user=user,
        query_text="Test question",
        result_type=SearchQuery.ResultType.FOUND,
    )
    query_id = query.id
    user.delete()
    assert not SearchQuery.objects.filter(id=query_id).exists()


@pytest.mark.django_db
def test_search_query_user_created_index_query_shape(firm, user):
    # Simulates the rate-limiting query: "how many rows for this user
    # in the last N seconds" — proves the (user, -created_at) index
    # supports a normal ordered filter without error.
    SearchQuery.objects.create(
        firm=firm, user=user, query_text="Q1",
        result_type=SearchQuery.ResultType.FOUND,
    )
    SearchQuery.objects.create(
        firm=firm, user=user, query_text="Q2",
        result_type=SearchQuery.ResultType.NOT_FOUND,
    )
    recent = SearchQuery.objects.filter(user=user).order_by("-created_at")
    assert recent.count() == 2
    assert recent.first().query_text == "Q2"


# ---------- Citation tests ----------

@pytest.mark.django_db
def test_citation_creation_valid(firm, user, chunk):
    query = SearchQuery.objects.create(
        firm=firm, user=user, query_text="Q1",
        result_type=SearchQuery.ResultType.FOUND,
    )
    citation = Citation.objects.create(
        search_query=query,
        chunk=chunk,
        relevance_score=0.87,
        rank=1,
    )
    assert citation.rank == 1


@pytest.mark.django_db
def test_citation_relevance_score_out_of_range_rejected(firm, user, chunk):
    query = SearchQuery.objects.create(
        firm=firm, user=user, query_text="Q1",
        result_type=SearchQuery.ResultType.FOUND,
    )
    with pytest.raises(IntegrityError):
        Citation.objects.create(
            search_query=query,
            chunk=chunk,
            relevance_score=1.5,
            rank=1,
        )


@pytest.mark.django_db
def test_citation_rank_must_be_at_least_1(firm, user, chunk):
    query = SearchQuery.objects.create(
        firm=firm, user=user, query_text="Q1",
        result_type=SearchQuery.ResultType.FOUND,
    )
    with pytest.raises(IntegrityError):
        Citation.objects.create(
            search_query=query,
            chunk=chunk,
            relevance_score=0.5,
            rank=0,
        )


@pytest.mark.django_db
def test_citation_same_chunk_cannot_be_cited_twice_for_same_query(firm, user, chunk):
    query = SearchQuery.objects.create(
        firm=firm, user=user, query_text="Q1",
        result_type=SearchQuery.ResultType.FOUND,
    )
    Citation.objects.create(
        search_query=query, chunk=chunk, relevance_score=0.9, rank=1,
    )
    with pytest.raises(IntegrityError):
        Citation.objects.create(
            search_query=query, chunk=chunk, relevance_score=0.5, rank=2,
        )


@pytest.mark.django_db
def test_citation_rank_must_be_unique_per_query(firm, user, document, chunk):
    query = SearchQuery.objects.create(
        firm=firm, user=user, query_text="Q1",
        result_type=SearchQuery.ResultType.FOUND,
    )
    second_chunk = Chunk.objects.create(
        document=document,
        firm=firm,
        page_number=2,
        chunk_index=1,
        content="A second, different clause.",
        token_count=6,
        embedding=[0.2] * 384,
    )
    Citation.objects.create(
        search_query=query, chunk=chunk, relevance_score=0.9, rank=1,
    )
    with pytest.raises(IntegrityError):
        Citation.objects.create(
            search_query=query, chunk=second_chunk, relevance_score=0.8, rank=1,
        )


@pytest.mark.django_db
def test_citation_deleted_when_chunk_deleted(firm, user, chunk):
    query = SearchQuery.objects.create(
        firm=firm, user=user, query_text="Q1",
        result_type=SearchQuery.ResultType.FOUND,
    )
    citation = Citation.objects.create(
        search_query=query, chunk=chunk, relevance_score=0.9, rank=1,
    )
    citation_id = citation.id
    chunk.delete()
    assert not Citation.objects.filter(id=citation_id).exists()