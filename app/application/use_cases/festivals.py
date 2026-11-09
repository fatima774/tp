"""Cas d'utilisation liés au festival et à la publication du planning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.dto import FestivalChange, FestivalView
from app.application.errors import NotFoundError
from app.application.events import EventDispatcher
from app.application.ports import UnitOfWork
from app.domain.festival import Festival
from app.domain.value_objects import FestivalPeriod


def load_festival(uow: UnitOfWork, festival_id: int) -> Festival:
    festival = uow.festivals.get(festival_id)
    if festival is None:
        raise NotFoundError("Festival introuvable")
    return festival


@dataclass(frozen=True)
class CreateFestivalCommand:
    name: str
    location: str
    start_date: datetime
    end_date: datetime


class CreateFestival:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, cmd: CreateFestivalCommand) -> FestivalView:
        festival = Festival.create(cmd.name, cmd.location, FestivalPeriod(cmd.start_date, cmd.end_date))
        with self.uow:
            self.uow.festivals.add(festival)
            self.uow.commit()
        return FestivalView.of(festival)


class ListFestivals:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self) -> list[FestivalView]:
        with self.uow:
            return [FestivalView.of(f) for f in self.uow.festivals.list()]


class GetFestival:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, festival_id: int) -> FestivalView:
        with self.uow:
            return FestivalView.of(load_festival(self.uow, festival_id))


class PublishPlanning:
    """Publier le planning (R8), puis notifier (défaut 2)."""

    def __init__(self, uow: UnitOfWork, dispatcher: EventDispatcher) -> None:
        self.uow = uow
        self.dispatcher = dispatcher

    def execute(self, festival_id: int) -> FestivalChange:
        with self.uow:
            festival = load_festival(self.uow, festival_id)
            artist_ids = {c.artist_id for c in festival.planning()}
            artists = self.uow.artists.get_many(artist_ids)
            festival.publish({a.id: a.required_equipment for a in artists.values()})
            self.uow.festivals.save(festival)
            self.uow.commit()
        # La publication est enregistrée : la notification ne peut plus l'annuler.
        status = self.dispatcher.dispatch(festival.pull_events())
        return FestivalChange(FestivalView.of(festival), status)


class UnpublishPlanning:
    """Procédure explicite pour rouvrir un planning publié (R7, défaut 3)."""

    def __init__(self, uow: UnitOfWork, dispatcher: EventDispatcher) -> None:
        self.uow = uow
        self.dispatcher = dispatcher

    def execute(self, festival_id: int) -> FestivalChange:
        with self.uow:
            festival = load_festival(self.uow, festival_id)
            festival.unpublish()
            self.uow.festivals.save(festival)
            self.uow.commit()
        status = self.dispatcher.dispatch(festival.pull_events())
        return FestivalChange(FestivalView.of(festival), status)
