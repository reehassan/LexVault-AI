# apps/documents/tests.py
import io

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.documents.models import Document
from apps.firms.models import Firm

User = get_user_model()


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


def make_pdf_bytes():
    # Minimal but real PDF structure — %PDF header plus enough
    # structure that PyMuPDF/libmagic both recognize it as a genuine PDF.
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"trailer<</Root 1 0 R>>"
    )


@pytest.mark.django_db
def test_upload_valid_pdf_creates_document(client_logged_in):
    pdf_file = io.BytesIO(make_pdf_bytes())
    pdf_file.name = "contract.pdf"

    response = client_logged_in.post(
        reverse("upload_document"),
        {"file": pdf_file},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "uploaded"
    assert Document.objects.filter(id=data["document_id"]).exists()


@pytest.mark.django_db
def test_upload_rejects_non_pdf_file(client_logged_in):
    fake_file = io.BytesIO(b"just some plain text, not a pdf at all")
    fake_file.name = "notes.txt"

    response = client_logged_in.post(
        reverse("upload_document"),
        {"file": fake_file},
    )

    assert response.status_code == 422


@pytest.mark.django_db
def test_upload_rejects_oversized_file(client_logged_in, settings):
    settings.MAX_DOCUMENT_UPLOAD_SIZE = 10  # bytes, artificially tiny for the test
    pdf_file = io.BytesIO(make_pdf_bytes())
    pdf_file.name = "contract.pdf"

    response = client_logged_in.post(
        reverse("upload_document"),
        {"file": pdf_file},
    )

    assert response.status_code == 413


@pytest.mark.django_db
def test_upload_rejects_empty_file(client_logged_in):
    empty_file = io.BytesIO(b"")
    empty_file.name = "empty.pdf"

    response = client_logged_in.post(
        reverse("upload_document"),
        {"file": empty_file},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_upload_requires_authentication():
    client = Client()  # not logged in
    pdf_file = io.BytesIO(make_pdf_bytes())
    pdf_file.name = "contract.pdf"

    response = client.post(
        reverse("upload_document"),
        {"file": pdf_file},
    )

    assert response.status_code == 401