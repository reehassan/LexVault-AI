import pytest
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from apps.firms.models import Firm
from apps.documents.models import Document, Chunk
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def firm(db):
    return Firm.objects.create(name="Test Firm")


@pytest.fixture
def user(firm):
    return User.objects.create_user(username="uploader", firm=firm, password="x")


@pytest.mark.django_db
def test_document_creation_defaults_to_uploaded_status(firm, user):
    doc = Document.objects.create(
        firm=firm,
        uploaded_by=user,
        filename="contract.pdf",
        file_size_bytes=1024,
        storage_path="/documents/contract.pdf",
    )
    assert doc.status == Document.ProcessingStatus.UPLOADED


@pytest.mark.django_db
def test_document_file_size_must_be_positive(firm, user):
    with pytest.raises(IntegrityError):
        Document.objects.create(
            firm=firm,
            uploaded_by=user,
            filename="bad.pdf",
            file_size_bytes=0,
            storage_path="/documents/bad.pdf",
        )


@pytest.mark.django_db
def test_document_page_count_cannot_be_negative(firm, user):
    with pytest.raises(IntegrityError):
        Document.objects.create(
            firm=firm,
            uploaded_by=user,
            filename="bad.pdf",
            file_size_bytes=1024,
            storage_path="/documents/bad.pdf",
            page_count=-1,
        )


@pytest.mark.django_db
def test_chunk_requires_positive_page_number(firm, user):
    doc = Document.objects.create(
        firm=firm, uploaded_by=user, filename="a.pdf",
        file_size_bytes=100, storage_path="/a.pdf",
    )
    with pytest.raises(IntegrityError):
        Chunk.objects.create(
            document=doc,
            firm=firm,
            page_number=0,
            chunk_index=0,
            content="Some chunk text",
            token_count=10,
            embedding=[0.1] * 384,
        )


@pytest.mark.django_db
def test_chunk_content_cannot_be_empty(firm, user):
    doc = Document.objects.create(
        firm=firm, uploaded_by=user, filename="a.pdf",
        file_size_bytes=100, storage_path="/a.pdf",
    )
    with pytest.raises(IntegrityError):
        Chunk.objects.create(
            document=doc,
            firm=firm,
            page_number=1,
            chunk_index=0,
            content="",
            token_count=10,
            embedding=[0.1] * 384,
        )


@pytest.mark.django_db
def test_chunk_unique_index_per_document(firm, user):
    doc = Document.objects.create(
        firm=firm, uploaded_by=user, filename="a.pdf",
        file_size_bytes=100, storage_path="/a.pdf",
    )
    Chunk.objects.create(
        document=doc, firm=firm, page_number=1, chunk_index=0,
        content="First chunk", token_count=5, embedding=[0.1] * 384,
    )
    with pytest.raises(IntegrityError):
        Chunk.objects.create(
            document=doc, firm=firm, page_number=1, chunk_index=0,
            content="Duplicate index chunk", token_count=5, embedding=[0.2] * 384,
        )


@pytest.mark.django_db
def test_chunk_firm_matches_document_firm_query(firm, user):
    doc = Document.objects.create(
        firm=firm, uploaded_by=user, filename="a.pdf",
        file_size_bytes=100, storage_path="/a.pdf",
    )
    Chunk.objects.create(
        document=doc, firm=firm, page_number=1, chunk_index=0,
        content="First chunk", token_count=5, embedding=[0.1] * 384,
    )

    firm_scoped_chunks = Chunk.objects.filter(firm=firm)
    assert firm_scoped_chunks.count() == 1
