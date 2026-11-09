"""Tests des cas d'utilisation avec des doubles en mémoire (ni SQLite, ni FastAPI).

On vérifie les décisions du cas d'utilisation : ce qui est enregistré (commit ou
pas), ce qui est envoyé au port de notification, et les erreurs renvoyées.
"""

from datetime import datetime

import pytest

from app.application.errors import AlreadyExistsError, InvalidReferenceError, NotFoundError
from app.application.events import EventDispatcher, NotificationStatus
from app.application.use_cases.catalog import AddStage, AddStageCommand, RegisterArtist, RegisterArtistCommand
from app.application.use_cases.concerts import (
    CancelConcert,
    GetPlanning,
    RescheduleConcert,
    RescheduleConcertCommand,
    ScheduleConcert,
    ScheduleConcertCommand,
)
from app.application.use_cases.festivals import PublishPlanning, UnpublishPlanning
from app.application.use_cases.incidents import ReportIncident, ReportIncidentCommand
from app.domain.errors import InvalidValueError, PlanningLockedError, SchedulingConflictError
from app.domain.events import ConcertRescheduled, PlanningPublished
from app.domain.festival import FestivalStatus
from tests.builders import CONCRETE, CRIMSON, IRON_VOW, MAINSTAGE, artist, at, festival, reference_planning
from tests.fakes import FakeUnitOfWork, RecordingNotifier


@pytest.fixture
def uow():
    u = FakeUnitOfWork()
    u.stored_festivals.items[1] = festival(reference_planning())
    for a in (artist(IRON_VOW, "Iron Vow"), artist(CRIMSON, "Crimson Engine"), artist(CONCRETE, "Concrete Reign")):
        u.stored_artists.items[a.id] = a
    u.stored_artists.next_id = 10
    return u


@pytest.fixture
def notifier():
    return RecordingNotifier()


def reschedule(uow, notifier, concert_id, start, end):
    cmd = RescheduleConcertCommand(concert_id, start, end)
    return RescheduleConcert(uow, EventDispatcher(notifier)).execute(cmd)


# ---------------------------------------------------------------- déplacer


class TestRescheduleConcert:
    def test_valid_move_is_committed_and_notified(self, uow, notifier):
        result = reschedule(uow, notifier, 11, at(18, 22), at(18, 23))
        assert result.concert.start_time == at(18, 22)
        assert result.notification_status is NotificationStatus.SENT
        assert uow.commits == 1
        assert uow.stored_festivals.items[1].find_concert(11).slot.start == at(18, 22)
        assert isinstance(notifier.events[0], ConcertRescheduled)

    def test_conflict_is_refused_nothing_saved_nothing_notified(self, uow, notifier):
        with pytest.raises(SchedulingConflictError):
            reschedule(uow, notifier, 11, at(18, 18, 30), at(18, 19, 15))
        assert uow.commits == 0
        assert notifier.events == []

    def test_invalid_slot_refused_before_loading(self, uow, notifier):
        with pytest.raises(InvalidValueError):
            reschedule(uow, notifier, 11, at(18, 20), at(18, 19))

    def test_unknown_concert(self, uow, notifier):
        with pytest.raises(NotFoundError):
            reschedule(uow, notifier, 999, at(18, 22), at(18, 23))

    def test_notification_failure_does_not_cancel_the_move(self, uow):
        """Défaut 2 : la modification est enregistrée, l'échec est signalé (pas d'exception)."""
        result = reschedule(uow, RecordingNotifier(fail=True), 11, at(18, 22), at(18, 23))
        assert result.notification_status is NotificationStatus.FAILED
        assert uow.commits == 1
        assert uow.stored_festivals.items[1].find_concert(11).slot.start == at(18, 22)

    def test_published_planning_is_locked(self, uow, notifier):
        """Défaut 3."""
        uow.stored_festivals.items[1].status = FestivalStatus.PUBLISHED
        with pytest.raises(PlanningLockedError):
            reschedule(uow, notifier, 11, at(18, 22), at(18, 23))
        assert uow.commits == 0


# ---------------------------------------------------------------- publier / dépublier


class TestPublication:
    def test_publish_commits_then_notifies(self, uow, notifier):
        result = PublishPlanning(uow, EventDispatcher(notifier)).execute(1)
        assert result.festival.status == "published"
        assert uow.stored_festivals.items[1].status is FestivalStatus.PUBLISHED
        assert isinstance(notifier.events[0], PlanningPublished)

    def test_publish_with_notification_failure_is_still_published(self, uow):
        result = PublishPlanning(uow, EventDispatcher(RecordingNotifier(fail=True))).execute(1)
        assert result.notification_status is NotificationStatus.FAILED
        assert uow.stored_festivals.items[1].status is FestivalStatus.PUBLISHED

    def test_unknown_festival(self, uow, notifier):
        with pytest.raises(NotFoundError):
            PublishPlanning(uow, EventDispatcher(notifier)).execute(999)

    def test_unpublish(self, uow, notifier):
        uow.stored_festivals.items[1].status = FestivalStatus.PUBLISHED
        UnpublishPlanning(uow, EventDispatcher(notifier)).execute(1)
        assert uow.stored_festivals.items[1].status is FestivalStatus.PREPARATION


# ---------------------------------------------------------------- programmer / annuler / consulter


class TestScheduleConcert:
    def test_schedule(self, uow):
        view = ScheduleConcert(uow).execute(ScheduleConcertCommand(1, CONCRETE, MAINSTAGE, at(19, 12), at(19, 13)))
        assert view.id is not None and view.festival_id == 1
        assert uow.commits == 1

    @pytest.mark.parametrize("festival_id,artist_id", [(999, IRON_VOW), (1, 999)])
    def test_r4_unknown_references(self, uow, festival_id, artist_id):
        with pytest.raises(InvalidReferenceError):
            ScheduleConcert(uow).execute(
                ScheduleConcertCommand(festival_id, artist_id, MAINSTAGE, at(19, 12), at(19, 13))
            )


def test_cancel_notifies(uow, notifier):
    result = CancelConcert(uow, EventDispatcher(notifier)).execute(10)
    assert result.concert.status == "cancelled"
    assert result.notification_status is NotificationStatus.SENT


def test_planning_is_chronological(uow):
    assert [c.id for c in GetPlanning(uow).execute(1)] == [12, 10, 11]


# ---------------------------------------------------------------- catalogue et incidents


def test_duplicate_artist_refused(uow):
    with pytest.raises(AlreadyExistsError):
        RegisterArtist(uow).execute(RegisterArtistCommand("Iron Vow", "Heavy"))


def test_r9_stage_capacity_checked_without_http(uow):
    with pytest.raises(InvalidValueError):
        AddStage(uow).execute(AddStageCommand(1, "Valley", 0))


def test_r10_incident_on_unknown_concert(uow):
    with pytest.raises(InvalidReferenceError):
        ReportIncident(uow).execute(ReportIncidentCommand(999, "Ampli en panne"))


def test_incident_uses_injected_clock(uow):
    fixed = datetime(2027, 6, 18, 18, 42)
    view = ReportIncident(uow, clock=lambda: fixed).execute(ReportIncidentCommand(10, "Ampli en panne"))
    assert view.occurred_at == fixed
    assert len(uow.stored_incidents.items) == 1
