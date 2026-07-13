"""
End-to-end test of everything built so far: HTTP upload -> MIME validation
-> storage -> Celery task trigger -> real PDF extraction -> Document status
update.

Relies on CELERY_TASK_ALWAYS_EAGER=True (config/settings/test.py), which
makes process_document.delay(...) run synchronously, in-process, as part
of the request itself — so by the time the response comes back, extraction
has genuinely already happened, not just been queued.
"""

import fitz
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.firms.models import Firm
from apps.documents.models import Document
from django.contrib.auth import get_user_model

User = get_user_model()


def build_pdf_bytes(pages_text: list[str]) -> bytes:
    """Build a real, valid multi-page PDF in memory using fitz itself."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def firm(db):
    return Firm.objects.create(name="Test Firm")


@pytest.fixture
def user(firm):
    return User.objects.create_user(username="uploader", firm=firm, password="x")


@pytest.fixture
def client_logged_in(user):
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_full_pipeline_upload_through_extraction(client_logged_in, firm):
    pdf_bytes = build_pdf_bytes(
        ["Page one content", "Page two content", "Page three content"]
    )
    pdf_file = SimpleUploadedFile(
        "multi_page.pdf", pdf_bytes, content_type="application/pdf"
    )

    response = client_logged_in.post("/documents/upload/", {"document": pdf_file})
    assert response.status_code == 201

    document = Document.objects.get(firm=firm, filename="multi_page.pdf")
    document.refresh_from_db()

    # If this passes, the entire chain actually ran for real:
    # view -> MIME check -> file saved to storage -> Document row created
    # -> process_document.delay() -> (eager) -> extract_pages() ->
    # page_count written back to the same Document row.
    assert document.status == Document.ProcessingStatus.PROCESSING
    assert document.page_count == 3


@pytest.mark.django_db
def test_full_pipeline_marks_failed_on_corrupted_upload(client_logged_in, firm):
    """
    A file that passes the MIME check (real %PDF- header) but is broken
    in a way PyMuPDF can't parse should end the pipeline in FAILED, with
    a real error_message — not crash, not silently succeed.
    """
    # Valid PDF header, but truncated/garbage body — passes python-magic's
    # header sniff, fails PyMuPDF's actual structural parse.
    broken_bytes = b"%PDF-1.4\n" + b"not a real pdf body" * 50
    pdf_file = SimpleUploadedFile(
        "broken.pdf", broken_bytes, content_type="application/pdf"
    )

    response = client_logged_in.post("/documents/upload/", {"document": pdf_file})
    assert response.status_code == 201  # upload itself succeeds — it's a valid MIME type

    document = Document.objects.get(firm=firm, filename="broken.pdf")
    document.refresh_from_db()

    assert document.status == Document.ProcessingStatus.FAILED
    assert document.error_message  # not empty — some message was recorded