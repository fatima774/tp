"""Objets-valeurs du domaine.

Un objet-valeur n'a pas d'identifiant : il est défini uniquement par ses valeurs.
Deux créneaux 18h-19h le même jour sont identiques, ce sont "les mêmes".

Ils sont immuables (frozen=True) et se valident à la création : il est donc
impossible d'avoir en mémoire un créneau dont la fin précède le début.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from app.domain.errors import InvalidValueError


def require_text(
    value: object,
    label: str,
    *,
    min_length: int = 1,
    max_length: int | None = None,
    rule: str | None = None,
) -> str:
    """Vérifie qu'un texte n'est pas vide (les espaces seuls ne comptent pas)."""
    if not isinstance(value, str):
        raise InvalidValueError(f"{label} doit être un texte", rule=rule)
    cleaned = value.strip()
    if not cleaned:
        raise InvalidValueError(f"{label} ne peut pas être vide", rule=rule)
    if len(cleaned) < min_length:
        raise InvalidValueError(
            f"{label} doit contenir au moins {min_length} caractères", rule=rule
        )
    if max_length is not None and len(cleaned) > max_length:
        raise InvalidValueError(
            f"{label} ne doit pas dépasser {max_length} caractères", rule=rule
        )
    return cleaned


def ensure_naive(*values: datetime) -> None:
    """Toutes les dates du domaine sont exprimées en heure locale du festival, sans fuseau.

    Mélanger des dates avec et sans fuseau provoquait une erreur 500 dans
    l'application initiale : on refuse explicitement ce cas.
    """
    for value in values:
        if not isinstance(value, datetime):
            raise InvalidValueError("Une date valide est attendue")
        if value.tzinfo is not None:
            raise InvalidValueError(
                "Les dates doivent être exprimées sans fuseau horaire (heure locale du festival)"
            )


@dataclass(frozen=True)
class TimeSlot:
    """Créneau : intervalle [début, fin[ d'un concert."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        ensure_naive(self.start, self.end)
        if self.end <= self.start:  # R1
            raise InvalidValueError(
                "L'heure de fin doit être strictement postérieure à l'heure de début",
                rule="R1",
            )

    def overlaps(self, other: TimeSlot) -> bool:
        """Deux créneaux se chevauchent s'ils ont une partie commune.

        Des créneaux qui se touchent (18h-19h puis 19h-20h) ne se chevauchent pas.
        """
        return self.start < other.end and other.start < self.end

    def __str__(self) -> str:
        return f"{self.start:%d/%m/%Y %H:%M} - {self.end:%d/%m/%Y %H:%M}"


@dataclass(frozen=True)
class FestivalPeriod:
    """Période pendant laquelle se déroule un festival."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        ensure_naive(self.start, self.end)
        if self.end <= self.start:
            raise InvalidValueError(
                "La date de fin doit être postérieure à la date de début"
            )

    def contains(self, slot: TimeSlot) -> bool:
        """R6 : un concert doit se dérouler entièrement dans la période du festival."""
        return self.start <= slot.start and slot.end <= self.end


@dataclass(frozen=True)
class EquipmentSet:
    """Ensemble d'équipements techniques (besoins d'un artiste ou dotation d'une scène)."""

    items: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def of(cls, names: Iterable[str] = ()) -> EquipmentSet:
        cleaned = {require_text(name, "Le nom d'un équipement") for name in names}
        return cls(frozenset(cleaned))

    def missing_from(self, available: EquipmentSet) -> frozenset[str]:
        """Équipements de cet ensemble que `available` ne fournit pas."""
        return self.items - available.items

    def is_covered_by(self, available: EquipmentSet) -> bool:
        return not self.missing_from(available)

    def as_sorted_list(self) -> list[str]:
        return sorted(self.items)


@dataclass(frozen=True)
class Capacity:
    """Capacité d'accueil d'une scène (R9 : strictement positive)."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise InvalidValueError("La capacité doit être un nombre entier", rule="R9")
        if self.value <= 0:
            raise InvalidValueError(
                "La capacité d'une scène doit être strictement positive", rule="R9"
            )
