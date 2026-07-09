import pytest
from apps.firms.models import Firm


@pytest.mark.django_db
def test_firm_creation():
    firm = Firm.objects.create(name="Test Firm")
    assert firm.name == "Test Firm"
    assert firm.id is not None
    assert firm.created_at is not None


@pytest.mark.django_db
def test_firm_str_representation():
    firm = Firm.objects.create(name="Acme Legal")
    assert str(firm) == "Acme Legal"


@pytest.mark.django_db
def test_firm_id_is_uuid():
    import uuid
    firm = Firm.objects.create(name="Test Firm")
    assert isinstance(firm.id, uuid.UUID)
