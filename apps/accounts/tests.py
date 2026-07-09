# apps/accounts/tests.py
import pytest
from django.contrib.auth import get_user_model
from apps.firms.models import Firm
from django.db import IntegrityError

User = get_user_model()

@pytest.mark.django_db
def test_firm_isolation_at_query_level():
    firm_a = Firm.objects.create(name="Firm A")
    firm_b = Firm.objects.create(name="Firm B")

    User.objects.create_user(username="alice", firm=firm_a, password="x")
    User.objects.create_user(username="bob", firm=firm_b, password="x")

    firm_a_users = User.objects.filter(firm=firm_a)
    assert firm_a_users.count() == 1
    assert firm_a_users.first().username == "alice"

@pytest.mark.django_db
def test_duplicate_username_allowed_across_firms():
    firm_a = Firm.objects.create(name="Firm A")
    firm_b = Firm.objects.create(name="Firm B")

    User.objects.create_user(username="admin", firm=firm_a, password="x")
    User.objects.create_user(username="admin", firm=firm_b, password="x")

    assert User.objects.filter(username="admin").count() == 2


@pytest.mark.django_db
def test_duplicate_username_blocked_within_same_firm():
    firm_a = Firm.objects.create(name="Firm A")
    User.objects.create_user(username="admin", firm=firm_a, password="x")

    with pytest.raises(IntegrityError):
        User.objects.create_user(username="admin", firm=firm_a, password="y")