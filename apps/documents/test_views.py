from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.firms.models import Firm
from apps.documents.models import Document
from django.contrib.auth import get_user_model

User = get_user_model()

VALID_PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R >>\n%%EOF"
)


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
def test_upload_valid_pdf_creates_document(client_logged_in, firm, user):
    pdf_file = SimpleUploadedFile(
        "contract.pdf", VALID_PDF_BYTES, content_type="application/pdf"
    )
    response = client_logged_in.post(
        "/documents/upload/", {"document": pdf_file}
    )

    assert response.status_code == 201
    assert Document.objects.filter(firm=firm, filename="contract.pdf").exists()


@pytest.mark.django_db
def test_upload_rejects_fake_pdf(client_logged_in):
    fake_file = SimpleUploadedFile(
        "fake.pdf", b"just plain text, not a real pdf", content_type="application/pdf"
    )
    response = client_logged_in.post(
        "/documents/upload/", {"document": fake_file}
    )

    assert response.status_code == 400
    assert Document.objects.count() == 0


@pytest.mark.django_db
def test_upload_requires_a_file(client_logged_in):
    response = client_logged_in.post("/documents/upload/", {})
    assert response.status_code == 400


@pytest.mark.django_db
def test_upload_enqueues_process_document_task(client_logged_in, firm, user):
    """
    Proves the view actually triggers the Celery task with the correct
    document_id — not just that a Document row was created.
    """
    pdf_file = SimpleUploadedFile(
        "contract.pdf", VALID_PDF_BYTES, content_type="application/pdf"
    )

    with patch("apps.documents.views.process_document.delay") as mock_delay:
        response = client_logged_in.post(
            "/documents/upload/", {"document": pdf_file}
        )

    assert response.status_code == 201
    document = Document.objects.get(firm=firm, filename="contract.pdf")

    mock_delay.assert_called_once_with(str(document.id))
