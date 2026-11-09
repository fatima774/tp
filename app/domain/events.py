"""Événements de domaine : des faits métier qui SE SONT produits (verbe au passé).

L'agrégat les enregistre au moment où il change d'état. Le cas d'utilisation
les récupère APRÈS l'enregistrement en base et les transmet au port de
notification. Le domaine ne sait pas qu'une notification existe : il se contente
de dire « ceci s'est passé ».
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.value_objects import TimeSlot


@dataclass(frozen=True)
class DomainEvent:
    festival_id: int | None


@dataclass(frozen=True)
class ConcertRescheduled(DomainEvent):
    concert_id: int | None
    previous_slot: TimeSlot
    new_slot: TimeSlot


@dataclass(frozen=True)
class ConcertCancelled(DomainEvent):
    concert_id: int | None


@dataclass(frozen=True)
class PlanningPublished(DomainEvent):
    festival_name: str


@dataclass(frozen=True)
class PlanningUnpublished(DomainEvent):
    festival_name: str
