import pytest

from app.domain.artist import Artist
from app.domain.errors import InvalidValueError
from app.domain.incident import Incident
from app.domain.value_objects import EquipmentSet
from tests.builders import at


def test_artist_name_is_trimmed():
    assert Artist.create("  Iron Vow ", "Heavy", EquipmentSet()).name == "Iron Vow"


def test_artist_blank_name_refused():
    with pytest.raises(InvalidValueError):
        Artist.create("   ", "Heavy", EquipmentSet())


@pytest.mark.parametrize("description", ["", "   ", "\n\t"])
def test_r10_incident_description_must_not_be_blank(description):
    with pytest.raises(InvalidValueError) as exc:
        Incident.report(1, description, at(18, 20))
    assert exc.value.rule == "R10"


def test_incident_is_created_unresolved():
    incident = Incident.report(1, "  Ampli en panne ", at(18, 20))
    assert incident.description == "Ampli en panne"
    assert incident.resolved is False
