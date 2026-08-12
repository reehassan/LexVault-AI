import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.firms.models import Firm


User = get_user_model()


@pytest.fixture
def firm(db):
    return Firm.objects.create(name="Test Firm")


@pytest.fixture
def user(firm):
    return User.objects.create_user(
        username="search_user",
        firm=firm,
        password="password123",
    )


@pytest.fixture
def client_logged_in(client, user):
    client.force_login(user)
    client._test_user = user
    return client


@pytest.mark.django_db
def test_search_requires_authentication(client):
    response = client.post(
        "/search/",
        data=json.dumps(
            {"question": "What are the payment terms?"}
        ),
        content_type="application/json",
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication required."
    }


@pytest.mark.django_db
def test_search_rejects_invalid_json(client_logged_in):
    response = client_logged_in.post(
        "/search/",
        data="{invalid json",
        content_type="application/json",
    )

    assert response.status_code == 400

    assert response.json() == {
        "detail": "Request body must contain valid JSON."
    }


@pytest.mark.django_db
def test_search_rejects_empty_question(
    client_logged_in,
    monkeypatch,
):
    from apps.search import views

    def fake_search_documents(*args, **kwargs):
        raise views.InvalidSearchQueryError(
            "question must be a non-empty string"
        )

    monkeypatch.setattr(
        views,
        "search_documents",
        fake_search_documents,
    )

    response = client_logged_in.post(
        "/search/",
        data=json.dumps({"question": ""}),
        content_type="application/json",
    )

    assert response.status_code == 400

    assert response.json() == {
        "detail": "question must be a non-empty string"
    }


@pytest.mark.django_db
def test_search_succeeds(
    client_logged_in,
    monkeypatch,
):
    from apps.search import views

    fake_results = [
        {
            "chunk_id": "chunk-1",
            "document_id": "document-1",
            "document_filename": "contract.pdf",
            "page_number": 3,
            "content": "Payment is due within thirty days.",
            "similarity": 0.91,
        },
        {
            "chunk_id": "chunk-2",
            "document_id": "document-1",
            "document_filename": "contract.pdf",
            "page_number": 5,
            "content": "Termination requires written notice.",
            "similarity": 0.84,
        },
    ]

    captured = {}

    def fake_search_documents(
        question,
        firm_id,
        top_k,
    ):
        captured["question"] = question
        captured["firm_id"] = firm_id
        captured["top_k"] = top_k

        return fake_results

    monkeypatch.setattr(
        views,
        "search_documents",
        fake_search_documents,
    )

    response = client_logged_in.post(
        "/search/",
        data=json.dumps(
            {
                "question": "What are the payment terms?"
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 2
    assert data["results"] == fake_results

    assert captured["question"] == (
        "What are the payment terms?"
    )

    assert captured["firm_id"] == client_logged_in._test_user.firm_id
    assert captured["top_k"] == 5


@pytest.mark.django_db
def test_search_returns_empty_results_for_empty_vault(
    client_logged_in,
    monkeypatch,
):
    from apps.search import views

    def fake_search_documents(*args, **kwargs):
        return []

    monkeypatch.setattr(
        views,
        "search_documents",
        fake_search_documents,
    )

    response = client_logged_in.post(
        "/search/",
        data=json.dumps(
            {"question": "What are the termination clauses?"}
        ),
        content_type="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["results"] == []
    assert data["count"] == 0


@pytest.mark.django_db
def test_search_rejects_user_without_firm(client, db):
    user = User.objects.create_user(
        username="no_firm_user",
        password="password123",
        firm=None,
    )

    client.force_login(user)

    response = client.post(
        "/search/",
        data=json.dumps(
            {"question": "What are the payment terms?"}
        ),
        content_type="application/json",
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": "User is not associated with a firm."
    }
