"""Tests unitaires des objets-valeurs : aucun FastAPI, aucune base de données."""

from datetime import UTC, datetime

import pytest

from app.domain.errors import InvalidValueError
from app.domain.value_objects import Capacity, EquipmentSet, FestivalPeriod, TimeSlot, require_text
from tests.builders import at, slot


class TestTimeSlot:
    def test_valid_slot(self):
        s = TimeSlot(at(18, 18), at(18, 19))
        assert s.start < s.end

    @pytest.mark.parametrize("end", [at(18, 18), at(18, 17)], ids=["fin=début", "fin<début"])
    def test_r1_end_must_be_strictly_after_start(self, end):
        with pytest.raises(InvalidValueError) as exc:
            TimeSlot(at(18, 18), end)
        assert exc.value.rule == "R1"

    def test_timezone_aware_dates_are_refused(self):
        with pytest.raises(InvalidValueError):
            TimeSlot(datetime(2027, 6, 18, 18, tzinfo=UTC), datetime(2027, 6, 18, 19, tzinfo=UTC))

    def test_overlap(self):
        assert slot(18, (18, 0), (19, 0)).overlaps(slot(18, (18, 30), (19, 30)))
        assert slot(18, (18, 0), (19, 0)).overlaps(slot(18, (17, 0), (20, 0)))  # inclus

    def test_adjacent_slots_do_not_overlap(self):
        assert not slot(18, (18, 0), (19, 0)).overlaps(slot(18, (19, 0), (20, 0)))

    def test_is_immutable(self):
        s = slot(18, (18, 0), (19, 0))
        with pytest.raises(AttributeError):
            s.start = at(18, 10)  # type: ignore[misc]

    def test_equality_by_value(self):
        assert slot(18, (18, 0), (19, 0)) == slot(18, (18, 0), (19, 0))


class TestFestivalPeriod:
    def test_end_after_start(self):
        with pytest.raises(InvalidValueError):
            FestivalPeriod(at(20, 10), at(19, 10))

    def test_r6_contains(self):
        period = FestivalPeriod(at(18, 10), at(20, 23, 59))
        assert period.contains(slot(18, (10, 0), (11, 0)))
        assert not period.contains(slot(18, (9, 0), (11, 0)))
        assert not period.contains(TimeSlot(at(20, 23), datetime(2027, 6, 21, 0, 30)))


class TestEquipmentSet:
    def test_cleans_names_and_removes_duplicates(self):
        assert EquipmentSet.of([" lights ", "lights"]).as_sorted_list() == ["lights"]

    def test_blank_name_refused(self):
        with pytest.raises(InvalidValueError):
            EquipmentSet.of(["  "])

    def test_r5_coverage(self):
        stage = EquipmentSet.of(["rigging", "lights"])
        assert EquipmentSet.of(["lights"]).is_covered_by(stage)
        assert EquipmentSet.of(["pyro"]).missing_from(stage) == {"pyro"}

    def test_name_with_comma_is_kept_whole(self):
        assert EquipmentSet.of(["a,b"]).as_sorted_list() == ["a,b"]


class TestCapacity:
    @pytest.mark.parametrize("value", [0, -1])
    def test_r9_must_be_strictly_positive(self, value):
        with pytest.raises(InvalidValueError) as exc:
            Capacity(value)
        assert exc.value.rule == "R9"

    def test_positive(self):
        assert Capacity(1).value == 1


def test_require_text_refuses_spaces_only():
    with pytest.raises(InvalidValueError):
        require_text("   ", "Le champ")
