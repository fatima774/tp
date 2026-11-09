"""Tests unitaires de l'agrégat Festival : règles de programmation et états du planning."""

import pytest

from app.domain.errors import (
    InvalidStatusTransitionError,
    MissingEquipmentError,
    OutsideFestivalPeriodError,
    PlanningLockedError,
    PlanningNotPublishableError,
    SchedulingConflictError,
    StageNotInFestivalError,
)
from app.domain.events import ConcertCancelled, ConcertRescheduled, PlanningPublished, PlanningUnpublished
from app.domain.festival import ConcertStatus, FestivalStatus
from app.domain.value_objects import EquipmentSet
from tests.builders import (
    CONCRETE,
    CRIMSON,
    IRON_VOW,
    MAINSTAGE,
    WARZONE,
    artist,
    concert,
    festival,
    reference_planning,
    slot,
)

ALL_REQUIREMENTS = {IRON_VOW: EquipmentSet(), CRIMSON: EquipmentSet(), CONCRETE: EquipmentSet()}


# ---------------------------------------------------------------- programmer


class TestScheduleConcert:
    def test_valid_concert_is_added(self):
        f = festival()
        c = f.schedule_concert(artist(), MAINSTAGE, slot(18, (18, 0), (19, 0)))
        assert c in f.concerts and c.status is ConcertStatus.SCHEDULED

    def test_r2_same_stage_overlap_refused(self):
        f = festival(reference_planning())
        with pytest.raises(SchedulingConflictError) as exc:
            f.schedule_concert(artist(CONCRETE, "Other"), MAINSTAGE, slot(18, (18, 30), (19, 15)))
        assert exc.value.rule == "R2"

    def test_r3_same_artist_on_two_stages_refused(self):
        f = festival(reference_planning())
        with pytest.raises(SchedulingConflictError) as exc:
            f.schedule_concert(artist(IRON_VOW), WARZONE, slot(18, (18, 30), (19, 30)))
        assert exc.value.rule == "R3"

    def test_r4_stage_of_another_festival_refused(self):
        with pytest.raises(StageNotInFestivalError):
            festival().schedule_concert(artist(), 999, slot(18, (18, 0), (19, 0)))

    def test_r5_missing_equipment_refused(self):
        with pytest.raises(MissingEquipmentError):
            festival().schedule_concert(artist(equipment=["large_rigging"]), WARZONE, slot(18, (18, 0), (19, 0)))

    def test_r6_outside_festival_refused(self):
        with pytest.raises(OutsideFestivalPeriodError):
            festival().schedule_concert(artist(), MAINSTAGE, slot(21, (18, 0), (19, 0)))

    def test_cancelled_concert_does_not_block_slot(self):
        f = festival([concert(10, CRIMSON, MAINSTAGE, slot(18, (18, 0), (19, 0)), cancelled=True)])
        f.schedule_concert(artist(), MAINSTAGE, slot(18, (18, 0), (19, 0)))

    def test_r7_refused_when_published(self):
        f = festival(status=FestivalStatus.PUBLISHED)
        with pytest.raises(PlanningLockedError):
            f.schedule_concert(artist(), MAINSTAGE, slot(18, (18, 0), (19, 0)))


# ---------------------------------------------------------------- déplacer (défaut 1)


class TestRescheduleConcert:
    def test_r2_move_onto_occupied_stage_refused(self):
        f = festival(reference_planning())
        with pytest.raises(SchedulingConflictError) as exc:
            f.reschedule_concert(11, slot(18, (18, 30), (19, 15)))
        assert exc.value.rule == "R2"
        assert f.find_concert(11).slot == slot(18, (19, 30), (20, 30))  # rien n'a changé
        assert f.pull_events() == []

    def test_r3_move_artist_onto_own_other_concert_refused(self):
        concerts = reference_planning() + [concert(13, IRON_VOW, WARZONE, slot(19, (14, 0), (15, 0)))]
        f = festival(concerts)
        with pytest.raises(SchedulingConflictError) as exc:
            f.reschedule_concert(13, slot(18, (18, 30), (19, 30)))
        assert exc.value.rule == "R3"

    def test_valid_move_is_accepted_and_emits_event(self):
        f = festival(reference_planning())
        new = slot(18, (22, 0), (23, 0))
        f.reschedule_concert(11, new)
        assert f.find_concert(11).slot == new
        [event] = f.pull_events()
        assert isinstance(event, ConcertRescheduled)
        assert event.concert_id == 11 and event.new_slot == new

    def test_concert_does_not_conflict_with_itself(self):
        f = festival(reference_planning())
        f.reschedule_concert(10, slot(18, (18, 15), (19, 15)))

    def test_r6_move_outside_festival_refused(self):
        with pytest.raises(OutsideFestivalPeriodError):
            festival(reference_planning()).reschedule_concert(10, slot(25, (18, 0), (19, 0)))

    def test_cancelled_concert_cannot_be_moved(self):
        f = festival([concert(10, IRON_VOW, MAINSTAGE, slot(18, (18, 0), (19, 0)), cancelled=True)])
        with pytest.raises(InvalidStatusTransitionError):
            f.reschedule_concert(10, slot(18, (20, 0), (21, 0)))

    def test_r7_move_refused_when_published(self):
        f = festival(reference_planning(), status=FestivalStatus.PUBLISHED)
        with pytest.raises(PlanningLockedError):
            f.reschedule_concert(10, slot(18, (22, 0), (23, 0)))


# ---------------------------------------------------------------- annuler


class TestCancelConcert:
    def test_cancel(self):
        f = festival(reference_planning())
        f.cancel_concert(10)
        assert f.find_concert(10).status is ConcertStatus.CANCELLED
        assert 10 not in [c.id for c in f.planning()]
        assert isinstance(f.pull_events()[0], ConcertCancelled)

    def test_cancel_twice_refused(self):
        f = festival(reference_planning())
        f.cancel_concert(10)
        with pytest.raises(InvalidStatusTransitionError):
            f.cancel_concert(10)

    def test_r7_cancel_refused_when_published(self):
        with pytest.raises(PlanningLockedError):
            festival(reference_planning(), status=FestivalStatus.PUBLISHED).cancel_concert(10)


# ---------------------------------------------------------------- publication (R7, R8)


class TestPublication:
    def test_publish_valid_planning(self):
        f = festival(reference_planning())
        f.publish(ALL_REQUIREMENTS)
        assert f.status is FestivalStatus.PUBLISHED
        assert isinstance(f.pull_events()[0], PlanningPublished)

    def test_publish_twice_refused(self):
        f = festival(reference_planning(), status=FestivalStatus.PUBLISHED)
        with pytest.raises(InvalidStatusTransitionError):
            f.publish(ALL_REQUIREMENTS)

    def test_r8_inconsistent_planning_cannot_be_published(self):
        """Planning incohérent (données héritées de l'ancienne version) : on liste toutes les violations."""
        bad = reference_planning() + [
            concert(20, CRIMSON, MAINSTAGE, slot(18, (18, 30), (19, 0))),  # R2 avec #10
            concert(21, IRON_VOW, WARZONE, slot(18, (18, 30), (19, 0))),  # R3 avec #10
            concert(22, CONCRETE, WARZONE, slot(25, (12, 0), (13, 0))),  # R6
        ]
        f = festival(bad)
        with pytest.raises(PlanningNotPublishableError) as exc:
            f.publish(ALL_REQUIREMENTS)
        rules = {v.split(" ")[0] for v in exc.value.violations}
        assert {"R2", "R3", "R6"} <= rules
        assert f.status is FestivalStatus.PREPARATION

    def test_r8_missing_equipment_detected_at_publication(self):
        f = festival([concert(10, IRON_VOW, WARZONE, slot(18, (18, 0), (19, 0)))])
        with pytest.raises(PlanningNotPublishableError) as exc:
            f.publish({IRON_VOW: EquipmentSet.of(["large_rigging"])})
        assert exc.value.violations[0].startswith("R5")

    def test_unpublish_then_modify_then_republish(self):
        """Procédure explicite retenue pour R7."""
        f = festival(reference_planning(), status=FestivalStatus.PUBLISHED)
        f.unpublish()
        assert f.status is FestivalStatus.PREPARATION
        f.reschedule_concert(11, slot(18, (22, 0), (23, 0)))
        f.publish(ALL_REQUIREMENTS)
        events = f.pull_events()
        assert [type(e) for e in events] == [PlanningUnpublished, ConcertRescheduled, PlanningPublished]

    def test_unpublish_when_not_published_refused(self):
        with pytest.raises(InvalidStatusTransitionError):
            festival().unpublish()


def test_planning_is_chronological_and_excludes_cancelled():
    concerts = reference_planning() + [concert(30, CRIMSON, WARZONE, slot(18, (12, 0), (13, 0)), cancelled=True)]
    assert [c.id for c in festival(concerts).planning()] == [12, 10, 11]
