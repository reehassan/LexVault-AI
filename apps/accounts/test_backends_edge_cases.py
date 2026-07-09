import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model

from apps.accounts.backends import FirmBackend
from apps.firms.models import Firm

User = get_user_model()


@pytest.mark.django_db
def test_authenticate_fails_closed_on_multiple_users_returned():
    """
    The (firm, username) UniqueConstraint makes this scenario impossible
    in practice — even bulk_create can't bypass it, confirmed by testing.
    This test instead verifies the backend's *defensive* handling of
    MultipleObjectsReturned by mocking the query directly, proving the
    fail-closed branch works even though the DB constraint should always
    prevent it from being reached in real usage.
    """
    firm = Firm.objects.create(name="Firm A")
    user = User.objects.create_user(username="alice", firm=firm, password="pass1")

    with patch.object(
        User.objects, "get", side_effect=User.MultipleObjectsReturned
    ):
        backend = FirmBackend()
        result = backend.authenticate(
            request=None, firm=firm, username="alice", password="pass1"
        )

    assert result is None


@pytest.mark.django_db
def test_get_user_returns_correct_user_by_pk():
    firm = Firm.objects.create(name="Firm A")
    user = User.objects.create_user(username="alice", firm=firm, password="pass1")

    backend = FirmBackend()
    result = backend.get_user(user.pk)

    assert result == user


@pytest.mark.django_db
def test_get_user_returns_none_for_nonexistent_pk():
    import uuid

    backend = FirmBackend()
    result = backend.get_user(uuid.uuid4())

    assert result is None


@pytest.mark.django_db
def test_authenticate_returns_none_when_firm_missing():
    backend = FirmBackend()
    result = backend.authenticate(
        request=None, firm=None, username="alice", password="pass1"
    )
    assert result is None


@pytest.mark.django_db
def test_authenticate_returns_none_when_username_missing():
    firm = Firm.objects.create(name="Firm A")
    backend = FirmBackend()
    result = backend.authenticate(
        request=None, firm=firm, username=None, password="pass1"
    )
    assert result is None
