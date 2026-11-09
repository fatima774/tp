"""Tests de l'adaptateur SQLAlchemy : l'agrégat est enregistré puis relu à l'identique."""

import pytest
from sqlalchemy import text

from app.adapters.outbound.persistence.repositories import decode_equipment, encode_equipment
from app.bootstrap import build_container
from app.domain.artist import Artist
from app.domain.festival import Festival, FestivalStatus
from app.domain.value_objects import Capacity, EquipmentSet, FestivalPeriod
from tests.builders import at, slot


@pytest.fixture
def container(settings):
    c = build_container(settings)
    c.create_schema()
    yield c
    c.engine.dispose()


def test_festival_aggregate_round_trip(container):
    with container.uow() as uow:
        band = Artist.create("Band", "Doom", EquipmentSet.of(["lights"]))
        uow.artists.add(band)
        f = Festival.create("Fest", "Bordeaux", FestivalPeriod(at(18, 10), at(20, 23)))
        uow.festivals.add(f)
        stage = f.add_stage("Main", Capacity(100), EquipmentSet.of(["lights", "a,b"]))
        uow.festivals.save(f)
        concert = f.schedule_concert(band, stage.id, slot(18, (20, 0), (21, 0)))
        uow.festivals.save(f)
        uow.commit()
        assert f.id and stage.id and concert.id  # identifiants recopiés depuis la base

    with container.uow() as uow:
        loaded = uow.festivals.get_by_concert(concert.id)
        assert loaded.id == f.id
        assert loaded.find_stage(stage.id).equipment == EquipmentSet.of(["lights", "a,b"])
        assert loaded.find_concert(concert.id).slot == slot(18, (20, 0), (21, 0))
        assert loaded.status is FestivalStatus.PREPARATION


def test_without_commit_nothing_is_saved(container):
    with container.uow() as uow:
        uow.festivals.add(Festival.create("Fest", "Bordeaux", FestivalPeriod(at(18, 10), at(20, 23))))
        # pas de commit
    with container.uow() as uow:
        assert uow.festivals.list() == []


def test_equipment_json_and_legacy_csv_format():
    assert decode_equipment(encode_equipment(EquipmentSet.of(["a,b", "c"]))) == EquipmentSet.of(["a,b", "c"])
    assert decode_equipment("large_rigging,special_lighting") == EquipmentSet.of(["large_rigging", "special_lighting"])
    assert decode_equipment("") == EquipmentSet()


def test_legacy_rows_are_readable(container):
    """Une base créée par la version initiale (équipements en CSV) reste lisible."""
    with container.engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO festivals (id, name, location, start_date, end_date, status) "
            "VALUES (1, 'Old', 'Clisson', '2027-06-18 10:00:00', '2027-06-20 23:59:00', 'preparation')"
        ))
        conn.execute(text(
            "INSERT INTO stages (id, festival_id, name, capacity, available_equipment) "
            "VALUES (1, 1, 'Main', 100, 'large_rigging,special_lighting')"
        ))
    with container.uow() as uow:
        assert uow.festivals.get(1).find_stage(1).equipment.as_sorted_list() == ["large_rigging", "special_lighting"]
