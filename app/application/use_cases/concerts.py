"""Cas d'utilisation de programmation : programmer, déplacer, annuler, consulter.

Chaque cas d'utilisation suit le même schéma :
  1. construire les objets-valeurs à partir de la commande (validation immédiate) ;
  2. charger l'agrégat via le port de repository ;
  3. appeler la méthode métier de l'agrégat (c'est elle qui applique les règles) ;
  4. enregistrer puis commiter ;
  5. APRÈS le commit seulement, transmettre les événements aux notifications.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.dto import ConcertChange, ConcertView
from app.application.errors import InvalidReferenceError, NotFoundError
from app.application.events import EventDispatcher
from app.application.ports import UnitOfWork
from app.application.use_cases.festivals import load_festival
from app.domain.festival import Festival
from app.domain.value_objects import TimeSlot


def load_festival_of_concert(uow: UnitOfWork, concert_id: int) -> Festival:
    festival = uow.festivals.get_by_concert(concert_id)
    if festival is None:
        raise NotFoundError("Concert introuvable")
    return festival


@dataclass(frozen=True)
class ScheduleConcertCommand:
    festival_id: int
    artist_id: int
    stage_id: int
    start_time: datetime
    end_time: datetime


class ScheduleConcert:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, cmd: ScheduleConcertCommand) -> ConcertView:
        slot = TimeSlot(cmd.start_time, cmd.end_time)  # R1
        with self.uow:
            festival = self.uow.festivals.get(cmd.festival_id)
            if festival is None:
                raise InvalidReferenceError("Festival introuvable", rule="R4")
            artist = self.uow.artists.get(cmd.artist_id)
            if artist is None:
                raise InvalidReferenceError("Artiste introuvable", rule="R4")
            concert = festival.schedule_concert(artist, cmd.stage_id, slot)  # R2 à R7
            self.uow.festivals.save(festival)
            self.uow.commit()
        return ConcertView.of(festival, concert)


@dataclass(frozen=True)
class RescheduleConcertCommand:
    concert_id: int
    start_time: datetime
    end_time: datetime


class RescheduleConcert:
    """Déplacer un concert : corrige les défauts 1, 2 et 3."""

    def __init__(self, uow: UnitOfWork, dispatcher: EventDispatcher) -> None:
        self.uow = uow
        self.dispatcher = dispatcher

    def execute(self, cmd: RescheduleConcertCommand) -> ConcertChange:
        slot = TimeSlot(cmd.start_time, cmd.end_time)  # R1
        with self.uow:
            festival = load_festival_of_concert(self.uow, cmd.concert_id)
            concert = festival.reschedule_concert(cmd.concert_id, slot)  # R2, R3, R6, R7
            self.uow.festivals.save(festival)
            self.uow.commit()
        # Le déplacement est enregistré. Une panne de notification est signalée, pas propagée.
        status = self.dispatcher.dispatch(festival.pull_events())
        return ConcertChange(ConcertView.of(festival, concert), status)


class CancelConcert:
    def __init__(self, uow: UnitOfWork, dispatcher: EventDispatcher) -> None:
        self.uow = uow
        self.dispatcher = dispatcher

    def execute(self, concert_id: int) -> ConcertChange:
        with self.uow:
            festival = load_festival_of_concert(self.uow, concert_id)
            concert = festival.cancel_concert(concert_id)  # R7
            self.uow.festivals.save(festival)
            self.uow.commit()
        status = self.dispatcher.dispatch(festival.pull_events())
        return ConcertChange(ConcertView.of(festival, concert), status)


class GetConcert:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, concert_id: int) -> ConcertView:
        with self.uow:
            festival = load_festival_of_concert(self.uow, concert_id)
            return ConcertView.of(festival, festival.find_concert(concert_id))


class GetPlanning:
    """Concerts actifs d'un festival, dans l'ordre chronologique."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, festival_id: int) -> list[ConcertView]:
        with self.uow:
            festival = load_festival(self.uow, festival_id)
            return [ConcertView.of(festival, c) for c in festival.planning()]
