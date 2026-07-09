import pytest
from django.contrib.auth import get_user_model
from apps.accounts.backends import FirmBackend
from apps.firms.models import Firm

User = get_user_model()


@pytest.mark.django_db
def test_authenticate_success_with_correct_firm_and_password():
    firm = Firm.objects.create(name="Firm A")
    user = User.objects.create_user(username="alice", firm=firm, password="correctpass")

    backend = FirmBackend()
    result = backend.authenticate(
        request=None, firm=firm, username="alice", password="correctpass"
    )

    assert result == user


@pytest.mark.django_db
def test_authenticate_fails_with_wrong_password():
    firm = Firm.objects.create(name="Firm A")
    User.objects.create_user(username="alice", firm=firm, password="correctpass")

    backend = FirmBackend()
    result = backend.authenticate(
        request=None, firm=firm, username="alice", password="wrongpass"
    )

    assert result is None


@pytest.mark.django_db
def test_authenticate_fails_with_wrong_firm():
    firm_a = Firm.objects.create(name="Firm A")
    firm_b = Firm.objects.create(name="Firm B")
    User.objects.create_user(username="alice", firm=firm_a, password="correctpass")

    backend = FirmBackend()
    result = backend.authenticate(
        request=None, firm=firm_b, username="alice", password="correctpass"
    )

    assert result is None


@pytest.mark.django_db
def test_authenticate_fails_for_nonexistent_user():
    firm = Firm.objects.create(name="Firm A")

    backend = FirmBackend()
    result = backend.authenticate(
        request=None, firm=firm, username="ghost", password="whatever"
    )

    assert result is None


@pytest.mark.django_db
def test_authenticate_allows_same_username_different_firm_correctly():
    firm_a = Firm.objects.create(name="Firm A")
    firm_b = Firm.objects.create(name="Firm B")
    user_a = User.objects.create_user(username="admin", firm=firm_a, password="passA")
    user_b = User.objects.create_user(username="admin", firm=firm_b, password="passB")

    backend = FirmBackend()

    result_a = backend.authenticate(
        request=None, firm=firm_a, username="admin", password="passA"
    )
    result_b = backend.authenticate(
        request=None, firm=firm_b, username="admin", password="passB"
    )

    assert result_a == user_a
    assert result_b == user_b
