import io

import fitz
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.documents.models import Document
from apps.documents.tasks import process_document
from apps.firms.models import Firm

User = get_user_model()


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


@pytest.fixture
def firm(db):
    return Firm.objects.create(name="Test Firm")


@pytest.fixture
def user(firm):
    return User.objects.create_user(username="uploader", firm=firm, password="x")


@pytest.fixture
def uploaded_document(firm, user, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    from apps.documents.services.storage import save_document_file

    file_obj = SimpleUploadedFile(
        "contract.pdf", make_real_pdf_bytes(num_pages=2), content_type="application/pdf"
    )
    storage_path = save_document_file(file_obj, firm.id)

    return Document.objects.create(
        firm=firm,
        uploaded_by=user,
        filename="contract.pdf",
        file_size_bytes=len(file_obj),
        storage_path=storage_path,
        status=Document.ProcessingStatus.UPLOADED,
    )


@pytest.fixture
def corrupted_document(firm, user, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    from apps.documents.services.storage import save_document_file

    file_obj = SimpleUploadedFile(
        "broken.pdf", make_corrupted_pdf_bytes(), content_type="application/pdf"
    )
    storage_path = save_document_file(file_obj, firm.id)

    return Document.objects.create(
        firm=firm,
        uploaded_by=user,
        filename="broken.pdf",
        file_size_bytes=len(file_obj),
        storage_path=storage_path,
        status=Document.ProcessingStatus.UPLOADED,
    )


@pytest.mark.django_db
def test_process_document_marks_ready_on_success(uploaded_document):
    process_document(str(uploaded_document.id))

    uploaded_document.refresh_from_db()
    assert uploaded_document.status == Document.ProcessingStatus.READY
    assert uploaded_document.page_count == 2
    assert not uploaded_document.error_message


@pytest.mark.django_db
def test_process_document_marks_failed_on_corrupted_pdf(corrupted_document):
    process_document(str(corrupted_document.id))

    corrupted_document.refresh_from_db()
    assert corrupted_document.status == Document.ProcessingStatus.FAILED
    assert corrupted_document.error_message
    assert "Unable to open PDF" in corrupted_document.error_message
