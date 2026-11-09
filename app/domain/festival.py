"""Agrégat Festival : le cœur du modèle.

Pourquoi le festival est la racine de l'agrégat :
- R2 (pas de chevauchement sur une scène) et R3 (pas d'artiste à deux endroits)
  ne peuvent être vérifiées qu'en voyant TOUS les concerts du festival en même temps ;
- R4 (la scène appartient au festival), R6 (le concert reste dans la période du
  festival) et R7/R8 (état du planning) dépendent du festival.

Toute modification du planning passe donc par les méthodes de Festival :
programmer, déplacer, annuler, publier, dépublier. Il n'existe pas d'autre façon
de modifier un concert, ce qui empêche de contourner les règles (c'était
justement le défaut 1 de la version initiale).

Scene et Concert sont des entités internes à l'agrégat : elles ont un
identifiant, mais on ne les modifie jamais directement depuis l'extérieur.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from itertools import combinations

from app.domain.artist import Artist
from app.domain.errors import (
    InvalidStatusTransitionError,
    InvalidValueError,
    MissingEquipmentError,
    OutsideFestivalPeriodError,
    PlanningLockedError,
    PlanningNotPublishableError,
    SchedulingConflictError,
    StageNotInFestivalError,
)
from app.domain.events import (
    ConcertCancelled,
    ConcertRescheduled,
    DomainEvent,
    PlanningPublished,
    PlanningUnpublished,
)
from app.domain.value_objects import (
    Capacity,
    EquipmentSet,
    FestivalPeriod,
    TimeSlot,
    require_text,
)


class FestivalStatus(str, Enum):
    """États du planning.

    Transitions autorisées :
        PREPARATION --publier--> PUBLISHED  (si le planning respecte R8)
        PUBLISHED --dépublier--> PREPARATION (procédure explicite de R7)
    """

    PREPARATION = "preparation"
    PUBLISHED = "published"


class ConcertStatus(str, Enum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


@dataclass(eq=False)
class Stage:
    """Entité Scène, interne à l'agrégat Festival."""

    id: int | None
    name: str
    capacity: Capacity
    equipment: EquipmentSet


@dataclass(eq=False)
class Concert:
    """Entité Concert, interne à l'agrégat Festival.

    Deux concerts aux mêmes horaires restent deux concerts distincts : c'est
    l'identifiant qui les distingue, pas leurs valeurs.
    """

    id: int | None
    artist_id: int
    stage_id: int
    slot: TimeSlot
    status: ConcertStatus = ConcertStatus.SCHEDULED

    @property
    def is_active(self) -> bool:
        return self.status is ConcertStatus.SCHEDULED


class Festival:
    def __init__(
        self,
        *,
        id: int | None,
        name: str,
        location: str,
        period: FestivalPeriod,
        status: FestivalStatus = FestivalStatus.PREPARATION,
        stages: Iterable[Stage] = (),
        concerts: Iterable[Concert] = (),
    ) -> None:
        self.id = id
        self.name = require_text(name, "Le nom du festival", min_length=2, max_length=120)
        self.location = require_text(location, "Le lieu", min_length=2, max_length=120)
        self.period = period
        self.status = status
        self._stages: list[Stage] = list(stages)
        self._concerts: list[Concert] = list(concerts)
        self._events: list[DomainEvent] = []

    @classmethod
    def create(cls, name: str, location: str, period: FestivalPeriod) -> Festival:
        return cls(id=None, name=name, location=location, period=period)

    # ------------------------------------------------------------------ lecture

    @property
    def stages(self) -> tuple[Stage, ...]:
        return tuple(self._stages)

    @property
    def concerts(self) -> tuple[Concert, ...]:
        return tuple(self._concerts)

    @property
    def is_published(self) -> bool:
        return self.status is FestivalStatus.PUBLISHED

    def find_stage(self, stage_id: int) -> Stage | None:
        return next((s for s in self._stages if s.id == stage_id), None)

    def find_concert(self, concert_id: int) -> Concert | None:
        return next((c for c in self._concerts if c.id == concert_id), None)

    def planning(self) -> list[Concert]:
        """Concerts actifs dans l'ordre chronologique."""
        active = [c for c in self._concerts if c.is_active]
        return sorted(active, key=lambda c: (c.slot.start, c.id or 0))

    # ------------------------------------------------------------------ scènes

    def add_stage(self, name: str, capacity: Capacity, equipment: EquipmentSet) -> Stage:
        """Ajouter une scène ne modifie pas le planning : autorisé même après publication."""
        stage = Stage(
            id=None,
            name=require_text(name, "Le nom de la scène", min_length=2, max_length=100),
            capacity=capacity,
            equipment=equipment,
        )
        self._stages.append(stage)
        return stage

    # ------------------------------------------------------------------ planning

    def schedule_concert(self, artist: Artist, stage_id: int, slot: TimeSlot) -> Concert:
        """Programmer un concert. Vérifie R4, R5, R6, R2, R3 et R7."""
        self._ensure_modifiable()
        stage = self._stage_or_fail(stage_id)
        self._ensure_within_period(slot)
        self._ensure_equipment(artist, stage)
        self._ensure_no_conflict(artist_id=artist.id, stage_id=stage_id, slot=slot)
        concert = Concert(id=None, artist_id=artist.id, stage_id=stage_id, slot=slot)
        self._concerts.append(concert)
        return concert

    def reschedule_concert(self, concert_id: int, new_slot: TimeSlot) -> Concert:
        """Déplacer un concert. Mêmes règles que la programmation (correction du défaut 1)."""
        self._ensure_modifiable()
        concert = self._concert_or_fail(concert_id)
        if not concert.is_active:
            raise InvalidStatusTransitionError("Un concert annulé ne peut pas être déplacé")
        self._ensure_within_period(new_slot)
        self._ensure_no_conflict(
            artist_id=concert.artist_id,
            stage_id=concert.stage_id,
            slot=new_slot,
            ignore=concert,
        )
        previous = concert.slot
        concert.slot = new_slot
        self._events.append(
            ConcertRescheduled(
                festival_id=self.id,
                concert_id=concert.id,
                previous_slot=previous,
                new_slot=new_slot,
            )
        )
        return concert

    def cancel_concert(self, concert_id: int) -> Concert:
        self._ensure_modifiable()
        concert = self._concert_or_fail(concert_id)
        if not concert.is_active:
            raise InvalidStatusTransitionError("Ce concert est déjà annulé")
        concert.status = ConcertStatus.CANCELLED
        self._events.append(ConcertCancelled(festival_id=self.id, concert_id=concert.id))
        return concert

    # ------------------------------------------------------------------ publication

    def publish(self, artist_requirements: Mapping[int, EquipmentSet]) -> None:
        """Publier le planning (R8).

        `artist_requirements` associe à chaque artiste programmé ses besoins
        techniques : l'artiste est un autre agrégat, le cas d'utilisation les
        fournit pour que R5 soit revérifiée au moment de la publication.
        """
        if self.is_published:
            raise InvalidStatusTransitionError("Le planning est déjà publié", rule="R7")
        violations = self.planning_violations(artist_requirements)
        if violations:
            raise PlanningNotPublishableError(violations)
        self.status = FestivalStatus.PUBLISHED
        self._events.append(PlanningPublished(festival_id=self.id, festival_name=self.name))

    def unpublish(self) -> None:
        """Procédure explicite de R7 : repasser en préparation pour pouvoir modifier."""
        if not self.is_published:
            raise InvalidStatusTransitionError("Le planning n'est pas publié", rule="R7")
        self.status = FestivalStatus.PREPARATION
        self._events.append(PlanningUnpublished(festival_id=self.id, festival_name=self.name))

    def planning_violations(self, artist_requirements: Mapping[int, EquipmentSet]) -> list[str]:
        """Liste toutes les règles de programmation non respectées (vide = planning valide).

        Les méthodes de l'agrégat empêchent déjà de créer un planning invalide, mais
        des données plus anciennes (créées par la version initiale) peuvent l'être :
        on revérifie tout avant de publier.
        """
        violations: list[str] = []
        concerts = self.planning()
        for c in concerts:
            stage = self.find_stage(c.stage_id)
            if stage is None:
                violations.append(f"R4 - concert #{c.id} : la scène #{c.stage_id} n'appartient pas au festival")
            if not self.period.contains(c.slot):
                violations.append(f"R6 - concert #{c.id} : en dehors de la période du festival")
            required = artist_requirements.get(c.artist_id)
            if required is None:
                violations.append(f"R4 - concert #{c.id} : l'artiste #{c.artist_id} est introuvable")
            elif stage is not None and not required.is_covered_by(stage.equipment):
                missing = ", ".join(sorted(required.missing_from(stage.equipment)))
                violations.append(f"R5 - concert #{c.id} : équipements manquants ({missing})")
        for a, b in combinations(concerts, 2):
            if not a.slot.overlaps(b.slot):
                continue
            if a.stage_id == b.stage_id:
                violations.append(f"R2 - concerts #{a.id} et #{b.id} : chevauchement sur la même scène")
            if a.artist_id == b.artist_id:
                violations.append(f"R3 - concerts #{a.id} et #{b.id} : l'artiste joue deux fois en même temps")
        return violations

    # ------------------------------------------------------------------ événements

    def pull_events(self) -> list[DomainEvent]:
        """Retourne les événements produits puis vide la liste (à appeler après le commit)."""
        events, self._events = self._events, []
        return events

    # ------------------------------------------------------------------ règles internes

    def _ensure_modifiable(self) -> None:
        if self.is_published:
            raise PlanningLockedError("Le planning est publié : dépubliez-le avant de le modifier")

    def _stage_or_fail(self, stage_id: int) -> Stage:
        stage = self.find_stage(stage_id)
        if stage is None:
            raise StageNotInFestivalError("La scène n'appartient pas à ce festival")
        return stage

    def _concert_or_fail(self, concert_id: int) -> Concert:
        concert = self.find_concert(concert_id)
        if concert is None:
            raise InvalidValueError("Ce concert n'appartient pas à ce festival", rule="R4")
        return concert

    def _ensure_within_period(self, slot: TimeSlot) -> None:
        if not self.period.contains(slot):
            raise OutsideFestivalPeriodError("Le concert doit se dérouler pendant le festival")

    @staticmethod
    def _ensure_equipment(artist: Artist, stage: Stage) -> None:
        missing = artist.required_equipment.missing_from(stage.equipment)
        if missing:
            raise MissingEquipmentError(
                f"La scène {stage.name} ne dispose pas des équipements requis : " + ", ".join(sorted(missing))
            )

    def _ensure_no_conflict(
        self,
        *,
        artist_id: int,
        stage_id: int,
        slot: TimeSlot,
        ignore: Concert | None = None,
    ) -> None:
        for other in self._concerts:
            if other is ignore or not other.is_active or not other.slot.overlaps(slot):
                continue
            if other.stage_id == stage_id:
                raise SchedulingConflictError(
                    f"Conflit : la scène est déjà occupée par le concert #{other.id} ({other.slot})",
                    rule="R2",
                )
            if other.artist_id == artist_id:
                raise SchedulingConflictError(
                    f"Conflit : l'artiste joue déjà pendant ce créneau (concert #{other.id}, {other.slot})",
                    rule="R3",
                )
