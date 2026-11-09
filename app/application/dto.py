"""Objets de résultat renvoyés par les cas d'utilisation.

Les cas d'utilisation renvoient des « vues » simples plutôt que les objets du
domaine : l'adaptateur HTTP n'a donc pas besoin de connaître l'agrégat, et on
ne risque pas de modifier un objet métier en dehors d'un cas d'utilisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.events import NotificationStatus
from app.domain.artist import Artist
from app.domain.festival import Concert, Festival, Stage
from app.domain.incident import Incident


@dataclass(frozen=True)
class FestivalView:
    id: int
    name: str
    location: str
    start_date: datetime
    end_date: datetime
    status: str

    @classmethod
    def of(cls, f: Festival) -> FestivalView:
        return cls(f.id, f.name, f.location, f.period.start, f.period.end, f.status.value)


@dataclass(frozen=True)
class StageView:
    id: int
    festival_id: int
    name: str
    capacity: int
    available_equipment: list[str]

    @classmethod
    def of(cls, festival: Festival, s: Stage) -> StageView:
        return cls(s.id, festival.id, s.name, s.capacity.value, s.equipment.as_sorted_list())


@dataclass(frozen=True)
class ArtistView:
    id: int
    name: str
    genre: str
    required_equipment: list[str]

    @classmethod
    def of(cls, a: Artist) -> ArtistView:
        return cls(a.id, a.name, a.genre, a.required_equipment.as_sorted_list())


@dataclass(frozen=True)
class ConcertView:
    id: int
    festival_id: int
    artist_id: int
    stage_id: int
    start_time: datetime
    end_time: datetime
    status: str

    @classmethod
    def of(cls, festival: Festival, c: Concert) -> ConcertView:
        return cls(
            c.id, festival.id, c.artist_id, c.stage_id, c.slot.start, c.slot.end, c.status.value
        )


@dataclass(frozen=True)
class IncidentView:
    id: int
    concert_id: int
    description: str
    occurred_at: datetime
    resolved: bool

    @classmethod
    def of(cls, i: Incident) -> IncidentView:
        return cls(i.id, i.concert_id, i.description, i.occurred_at, i.resolved)


@dataclass(frozen=True)
class ConcertChange:
    """Résultat d'une modification de concert : le concert ET l'état de la notification."""

    concert: ConcertView
    notification_status: NotificationStatus


@dataclass(frozen=True)
class FestivalChange:
    festival: FestivalView
    notification_status: NotificationStatus
