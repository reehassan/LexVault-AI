# apps/documents/tests/test_pipeline.py
"""
Integration tests for process_document — the Celery task that runs the
full ingestion pipeline (extract -> chunk -> embed -> store -> ready/failed).

Unlike test_extractor.py, test_chunker.py, and test_embedder.py, which
test those pure functions in isolation, this file exercises the whole
task: real Document rows, real file storage, real calls into every
service together. Proves the pieces work as a pipeline, not just
individually.

Covers: successful processing (incl. chunk/embedding persistence),
corrupted/encrypted/empty PDF failure paths, zero-chunk failure,
transactional rollback on mid-pipeline failure, and cross-firm
isolation during processing.
"""
import io

import fitz
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.documents.models import Chunk, Document
from apps.documents.tasks import process_document
from apps.documents.services.storage import save_document_file
from apps.firms.models import Firm

User = get_user_model()


# ---------- PDF byte helpers ----------

def make_real_pdf_bytes(num_pages=2):
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text((50, 50), f"Real content on page {i + 1}.")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_corrupted_pdf_bytes():
    return b"%PDF-1.4\nnot a real pdf body at all"


def make_encrypted_pdf_bytes():
    doc = fitz.open()
    doc.new_page()
    buf = io.BytesIO()
    doc.save(buf, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="ownerpass", user_pw="userpass")
    doc.close()
    return buf.getvalue()


def make_empty_pdf_bytes():
    doc = fitz.open()
    doc.new_page()  # blank, no insert_text call
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


# ---------- Fixtures ----------

@pytest.fixture
def firm(db):
    return Firm.objects.create(name="Test Firm")


@pytest.fixture
def user(firm):
    return User.objects.create_user(username="uploader", firm=firm, password="x")


@pytest.fixture
def uploaded_document(firm, user, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    file_obj = SimpleUploadedFile(
        "contract.pdf", make_real_pdf_bytes(num_pages=2), content_type="application/pdf"
    )
    storage_path = save_document_file(file_obj, firm.id)
    return Document.objects.create(
        firm=firm, uploaded_by=user, filename="contract.pdf",
        file_size_bytes=len(file_obj), storage_path=storage_path,
        status=Document.ProcessingStatus.UPLOADED,
    )


@pytest.fixture
def corrupted_document(firm, user, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    file_obj = SimpleUploadedFile(
        "broken.pdf", make_corrupted_pdf_bytes(), content_type="application/pdf"
    )
    storage_path = save_document_file(file_obj, firm.id)
    return Document.objects.create(
        firm=firm, uploaded_by=user, filename="broken.pdf",
        file_size_bytes=len(file_obj), storage_path=storage_path,
        status=Document.ProcessingStatus.UPLOADED,
    )


@pytest.fixture
def encrypted_document(firm, user, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    file_obj = SimpleUploadedFile(
        "encrypted.pdf", make_encrypted_pdf_bytes(), content_type="application/pdf"
    )
    storage_path = save_document_file(file_obj, firm.id)
    return Document.objects.create(
        firm=firm, uploaded_by=user, filename="encrypted.pdf",
        file_size_bytes=len(file_obj), storage_path=storage_path,
        status=Document.ProcessingStatus.UPLOADED,
    )


@pytest.fixture
def empty_document(firm, user, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    file_obj = SimpleUploadedFile(
        "empty.pdf", make_empty_pdf_bytes(), content_type="application/pdf"
    )
    storage_path = save_document_file(file_obj, firm.id)
    return Document.objects.create(
        firm=firm, uploaded_by=user, filename="empty.pdf",
        file_size_bytes=len(file_obj), storage_path=storage_path,
        status=Document.ProcessingStatus.UPLOADED,
    )


# ---------- Tests: success path ----------

@pytest.mark.django_db
def test_process_document_marks_ready_on_success(uploaded_document):
    process_document(str(uploaded_document.id))

    uploaded_document.refresh_from_db()
    assert uploaded_document.status == Document.ProcessingStatus.READY
    assert uploaded_document.page_count == 2
    assert not uploaded_document.error_message

    chunks = Chunk.objects.filter(document=uploaded_document)
    assert chunks.count() > 0
    for chunk in chunks:
        assert chunk.firm_id == uploaded_document.firm_id
        assert len(chunk.embedding) == 384
        assert chunk.content


# ---------- Tests: extraction failure paths ----------

@pytest.mark.django_db
def test_process_document_marks_failed_on_corrupted_pdf(corrupted_document):
    process_document(str(corrupted_document.id))

    corrupted_document.refresh_from_db()
    assert corrupted_document.status == Document.ProcessingStatus.FAILED
    assert corrupted_document.error_message
    assert "Unable to open PDF" in corrupted_document.error_message
    assert Chunk.objects.filter(document=corrupted_document).count() == 0


@pytest.mark.django_db
def test_process_document_marks_failed_on_encrypted_pdf(encrypted_document):
    process_document(str(encrypted_document.id))

    encrypted_document.refresh_from_db()
    assert encrypted_document.status == Document.ProcessingStatus.FAILED
    assert "encrypted" in encrypted_document.error_message.lower()
    assert Chunk.objects.filter(document=encrypted_document).count() == 0


@pytest.mark.django_db
def test_process_document_marks_failed_on_empty_pdf(empty_document):
    process_document(str(empty_document.id))

    empty_document.refresh_from_db()
    assert empty_document.status == Document.ProcessingStatus.FAILED
    assert empty_document.error_message
    assert Chunk.objects.filter(document=empty_document).count() == 0


# ---------- Tests: zero-chunk failure ----------

@pytest.mark.django_db
def test_process_document_marks_failed_when_no_chunks_produced(uploaded_document, mocker):
    mocker.patch(
        "apps.documents.tasks.chunk_pages",
        return_value=[],
    )

    process_document(str(uploaded_document.id))

    uploaded_document.refresh_from_db()
    assert uploaded_document.status == Document.ProcessingStatus.FAILED
    assert "chunk" in uploaded_document.error_message.lower()
    assert Chunk.objects.filter(document=uploaded_document).count() == 0


# ---------- Tests: transactional integrity ----------
@pytest.mark.django_db(transaction=True)
def test_process_document_rolls_back_chunks_if_status_update_fails(uploaded_document, mocker):
    """
    Forces a failure INSIDE the atomic() block, after bulk_create()
    but before the status update completes, by making document.save()
    raise on its second call. Proves the whole block is one real
    transaction: uses transaction=True specifically because the
    default django_db fixture wraps every test in its own outer
    transaction, which would mask the result — a naive version of
    this test could pass even if atomic() were removed entirely.

    process_document's own broad except-Exception handler catches
    this failure and marks the document FAILED (that's correct,
    expected behavior from Day 17/18) — so this test does NOT expect
    the exception to propagate out. What it actually proves is that
    the bulk_create() that ran before the forced failure was rolled
    back by atomic(), leaving zero orphaned Chunk rows.
    """
    original_save = Document.save
    call_count = {"n": 0}

    def failing_save(self, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise Exception("Simulated DB failure during status update")
        return original_save(self, *args, **kwargs)

    mocker.patch.object(Document, "save", failing_save)

    process_document(str(uploaded_document.id))

    uploaded_document.refresh_from_db()
    assert uploaded_document.status == Document.ProcessingStatus.FAILED
    assert Chunk.objects.filter(document=uploaded_document).count() == 0

# ---------- Tests: tenant isolation ----------

@pytest.mark.django_db
def test_process_document_stays_scoped_to_its_own_firm(firm, user, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)

    firm_b = Firm.objects.create(name="Firm B")
    user_b = User.objects.create_user(username="uploader_b", firm=firm_b, password="x")

    file_a = SimpleUploadedFile("a.pdf", make_real_pdf_bytes(num_pages=1), content_type="application/pdf")
    path_a = save_document_file(file_a, firm.id)
    doc_a = Document.objects.create(
        firm=firm, uploaded_by=user, filename="a.pdf",
        file_size_bytes=len(file_a), storage_path=path_a,
        status=Document.ProcessingStatus.UPLOADED,
    )

    file_b = SimpleUploadedFile("b.pdf", make_real_pdf_bytes(num_pages=3), content_type="application/pdf")
    path_b = save_document_file(file_b, firm_b.id)
    doc_b = Document.objects.create(
        firm=firm_b, uploaded_by=user_b, filename="b.pdf",
        file_size_bytes=len(file_b), storage_path=path_b,
        status=Document.ProcessingStatus.UPLOADED,
    )

    process_document(str(doc_a.id))
    process_document(str(doc_b.id))

    doc_a.refresh_from_db()
    doc_b.refresh_from_db()

    assert doc_a.status == Document.ProcessingStatus.READY
    assert doc_a.page_count == 1
    assert doc_b.status == Document.ProcessingStatus.READY
    assert doc_b.page_count == 3
    assert str(firm.id) in doc_a.storage_path
    assert str(firm_b.id) in doc_b.storage_path
    assert str(firm.id) not in doc_b.storage_path

    # chunks must stay scoped too — Firm A's chunks reference Firm A,
    # never Firm B, and vice versa
    chunks_a = Chunk.objects.filter(document=doc_a)
    chunks_b = Chunk.objects.filter(document=doc_b)
    assert chunks_a.count() > 0
    assert chunks_b.count() > 0
    assert all(c.firm_id == firm.id for c in chunks_a)
    assert all(c.firm_id == firm_b.id for c in chunks_b)