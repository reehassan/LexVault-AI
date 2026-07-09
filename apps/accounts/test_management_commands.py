import pytest
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth import get_user_model

from apps.firms.models import Firm

User = get_user_model()


@pytest.mark.django_db
def test_createfirm_creates_firm():
    out = StringIO()
    call_command("createfirm", "--name", "New Test Firm", stdout=out)

    assert Firm.objects.filter(name="New Test Firm").exists()
    assert "New Test Firm" in out.getvalue()


@pytest.mark.django_db
def test_createfirmadmin_creates_superuser_for_firm():
    firm = Firm.objects.create(name="Firm A")
    out = StringIO()

    call_command(
        "createfirmadmin",
        "--firm", str(firm.id),
        "--username", "admintest",
        "--email", "admintest@example.com",
        "--password", "somepassword",
        stdout=out,
    )

    user = User.objects.get(username="admintest", firm=firm)
    assert user.is_superuser is True
    assert user.is_staff is True
    assert user.check_password("somepassword")


@pytest.mark.django_db
def test_createfirmadmin_fails_for_nonexistent_firm():
    import uuid

    with pytest.raises(CommandError, match="Firm not found"):
        call_command(
            "createfirmadmin",
            "--firm", str(uuid.uuid4()),
            "--username", "ghost",
            "--email", "ghost@example.com",
            "--password", "pass",
        )


@pytest.mark.django_db
def test_createfirmadmin_blocks_duplicate_username_in_same_firm():
    firm = Firm.objects.create(name="Firm A")
    call_command(
        "createfirmadmin",
        "--firm", str(firm.id),
        "--username", "dupe",
        "--email", "dupe1@example.com",
        "--password", "pass1",
    )

    with pytest.raises(CommandError, match="already exists in this firm"):
        call_command(
            "createfirmadmin",
            "--firm", str(firm.id),
            "--username", "dupe",
            "--email", "dupe2@example.com",
            "--password", "pass2",
        )


@pytest.mark.django_db
def test_createfirmadmin_allows_same_username_across_different_firms():
    firm_a = Firm.objects.create(name="Firm A")
    firm_b = Firm.objects.create(name="Firm B")

    call_command(
        "createfirmadmin",
        "--firm", str(firm_a.id),
        "--username", "shared",
        "--email", "a@example.com",
        "--password", "pass1",
    )
    call_command(
        "createfirmadmin",
        "--firm", str(firm_b.id),
        "--username", "shared",
        "--email", "b@example.com",
        "--password", "pass2",
    )

    assert User.objects.filter(username="shared").count() == 2
