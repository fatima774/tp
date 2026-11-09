"""Cas d'utilisation des incidents."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.application.dto import IncidentView
from app.application.errors import InvalidReferenceError
from app.application.ports import UnitOfWork
from app.domain.incident import Incident

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class ReportIncidentCommand:
    concert_id: int
    description: str
    occurred_at: datetime | None = None


class ReportIncident:
    def __init__(self, uow: UnitOfWork, clock: Clock = datetime.now) -> None:
        self.uow = uow
        self.clock = clock  # injectée pour pouvoir figer l'heure dans les tests

    def execute(self, cmd: ReportIncidentCommand) -> IncidentView:
        incident = Incident.report(
            cmd.concert_id, cmd.description, cmd.occurred_at or self.clock()
        )  # R10 : description non vide
        with self.uow:
            if self.uow.festivals.get_by_concert(cmd.concert_id) is None:
                raise InvalidReferenceError("Concert introuvable", rule="R10")  # R10 : concert existant
            self.uow.incidents.add(incident)
            self.uow.commit()
        return IncidentView.of(incident)


class ListIncidents:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, concert_id: int | None = None) -> list[IncidentView]:
        with self.uow:
            return [IncidentView.of(i) for i in self.uow.incidents.list(concert_id)]
