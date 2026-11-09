"""Tests de non-régression des trois défauts initiaux.

Ils rejouent par l'API HTTP, sur le jeu de données de démonstration, les
scénarios qui posaient problème dans la version initiale. Sur l'ancien code,
ils échouaient (voir docs/NOTE_ARCHITECTURE.md, section « Preuve avant/après »).

Rappel du jeu de données (18/06/2027) :
  #1 Iron Vow        Mainstage 18:00-19:00
  #2 Crimson Engine  Mainstage 19:30-20:30
  #4 Concrete Reign  Warzone   17:00-17:45
  #14 Crimson Engine Mainstage 20/06 20:00-21:00
"""

import pytest

from tests.fakes import RecordingNotifier


def move(client, concert_id, start, end):
    return client.patch(f"/concerts/{concert_id}/reschedule", json={"start_time": start, "end_time": end})


# ---------------------------------------------------------------- défaut 1


class TestDefect1Conflicts:
    def test_move_onto_occupied_stage_is_refused(self, seeded_client):
        before = seeded_client.get("/concerts/2").json()
        r = move(seeded_client, 2, "2027-06-18T18:30:00", "2027-06-18T19:15:00")
        assert r.status_code == 409
        assert r.json()["rule"] == "R2"
        assert seeded_client.get("/concerts/2").json() == before

    def test_artist_cannot_play_on_two_stages_at_once(self, seeded_client):
        """R3 : Crimson Engine joue sur la Mainstage le 20/06 de 20h à 21h (#14).
        On lui programme un concert sur la Warzone à midi, puis on essaie de le déplacer à 20h15."""
        created = seeded_client.post(
            "/concerts",
            json={
                "festival_id": 1,
                "artist_id": 2,
                "stage_id": 2,  # Crimson Engine, Warzone, 20/06 12h-13h
                "start_time": "2027-06-20T12:00:00",
                "end_time": "2027-06-20T13:00:00",
            },
        )
        assert created.status_code == 201
        warzone_id = created.json()["id"]
        r = move(seeded_client, warzone_id, "2027-06-20T20:15:00", "2027-06-20T20:45:00")  # #14 Mainstage 20h-21h
        assert r.status_code == 409
        assert r.json()["rule"] == "R3"

    def test_valid_move_is_accepted(self, seeded_client):
        r = move(seeded_client, 2, "2027-06-18T22:30:00", "2027-06-18T23:30:00")
        assert r.status_code == 200
        assert r.json()["start_time"] == "2027-06-18T22:30:00"

    def test_move_outside_festival_is_refused(self, seeded_client):
        r = move(seeded_client, 3, "2030-01-01T10:00:00", "2030-01-01T11:00:00")
        assert r.status_code == 400 and r.json()["rule"] == "R6"


# ---------------------------------------------------------------- défaut 2


class TestDefect2NotificationFailure:
    @pytest.fixture
    def notifier(self):
        return RecordingNotifier(fail=True)

    def test_move_is_saved_and_failure_is_reported_not_500(self, seeded_client):
        r = move(seeded_client, 2, "2027-06-18T22:30:00", "2027-06-18T23:30:00")
        assert r.status_code == 200
        assert r.json()["notification_status"] == "failed"
        assert seeded_client.get("/concerts/2").json()["start_time"] == "2027-06-18T22:30:00"

    def test_publication_is_saved_and_failure_is_reported_not_500(self, seeded_client):
        r = seeded_client.post("/festivals/1/publish")
        assert r.status_code == 200
        assert r.json()["status"] == "published"
        assert r.json()["notification_status"] == "failed"

    def test_refused_move_sends_nothing(self, seeded_client, notifier):
        notifier.fail = False
        move(seeded_client, 2, "2027-06-18T18:30:00", "2027-06-18T19:15:00")
        assert notifier.events == []


def test_successful_notification_is_reported(seeded_client, notifier):
    r = move(seeded_client, 2, "2027-06-18T22:30:00", "2027-06-18T23:30:00")
    assert r.json()["notification_status"] == "sent"
    assert len(notifier.events) == 1


# ---------------------------------------------------------------- défaut 3


class TestDefect3PublishedPlanning:
    @pytest.fixture
    def published(self, seeded_client):
        assert seeded_client.post("/festivals/1/publish").status_code == 200
        return seeded_client

    def test_move_after_publication_is_refused(self, published):
        before = published.get("/concerts/4").json()
        r = move(published, 4, "2027-06-18T16:00:00", "2027-06-18T16:45:00")
        assert r.status_code == 409 and r.json()["rule"] == "R7"
        assert published.get("/concerts/4").json() == before

    def test_cancel_and_create_after_publication_are_refused(self, published):
        assert published.post("/concerts/5/cancel").status_code == 409
        r = published.post(
            "/concerts",
            json={
                "festival_id": 1,
                "artist_id": 8,
                "stage_id": 2,
                "start_time": "2027-06-20T10:00:00",
                "end_time": "2027-06-20T11:00:00",
            },
        )
        assert r.status_code == 409

    def test_publish_twice_is_refused(self, published):
        assert published.post("/festivals/1/publish").status_code == 409

    def test_explicit_procedure_unpublish_modify_republish(self, published):
        assert published.post("/festivals/1/unpublish").json()["status"] == "preparation"
        assert move(published, 4, "2027-06-18T16:00:00", "2027-06-18T16:45:00").status_code == 200
        assert published.post("/festivals/1/publish").json()["status"] == "published"


def test_r8_inconsistent_legacy_planning_cannot_be_published(seeded_client, settings):
    """Une base remplie par l'ancienne version peut contenir des conflits : la publication les détecte."""
    from sqlalchemy import create_engine, text

    engine = create_engine(settings.database_url)
    with engine.begin() as conn:  # crée un chevauchement directement en base, comme l'ancien défaut 1
        conn.execute(
            text("UPDATE concerts SET start_time='2027-06-18 18:30:00', end_time='2027-06-18 19:15:00' WHERE id=2")
        )
    engine.dispose()
    r = seeded_client.post("/festivals/1/publish")
    assert r.status_code == 409
    assert r.json()["rule"] == "R8"
    assert any(v.startswith("R2") for v in r.json()["violations"])
    assert seeded_client.get("/festivals/1").json()["status"] == "preparation"
