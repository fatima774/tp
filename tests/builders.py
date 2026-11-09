"""Fabriques d'objets métier pour écrire des tests courts et lisibles."""

from __future__ import annotations

from datetime import datetime

from app.domain.artist import Artist
from app.domain.festival import Concert, ConcertStatus, Festival, FestivalStatus, Stage
from app.domain.value_objects import Capacity, EquipmentSet, FestivalPeriod, TimeSlot

MAINSTAGE, WARZONE = 1, 2
IRON_VOW, CRIMSON, CONCRETE = 1, 2, 3


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """Date du festival (juin 2027)."""
    return datetime(2027, 6, day, hour, minute)


def slot(day: int, start: tuple[int, int], end: tuple[int, int]) -> TimeSlot:
    return TimeSlot(at(day, *start), at(day, *end))


def artist(id: int = IRON_VOW, name: str = "Iron Vow", equipment=()) -> Artist:
    return Artist(id=id, name=name, genre="Heavy metal", required_equipment=EquipmentSet.of(equipment))


def concert(id: int, artist_id: int, stage_id: int, s: TimeSlot, cancelled: bool = False) -> Concert:
    status = ConcertStatus.CANCELLED if cancelled else ConcertStatus.SCHEDULED
    return Concert(id=id, artist_id=artist_id, stage_id=stage_id, slot=s, status=status)


def festival(concerts=(), status: FestivalStatus = FestivalStatus.PREPARATION) -> Festival:
    """Festival du 18/06 10h au 20/06 23h59, avec Mainstage (rigging + lumières) et Warzone (lumières)."""
    return Festival(
        id=1,
        name="Hellforge Open Air",
        location="Clisson",
        period=FestivalPeriod(at(18, 10), at(20, 23, 59)),
        status=status,
        stages=[
            Stage(MAINSTAGE, "Mainstage", Capacity(50000), EquipmentSet.of(["large_rigging", "special_lighting"])),
            Stage(WARZONE, "Warzone", Capacity(15000), EquipmentSet.of(["special_lighting"])),
        ],
        concerts=list(concerts),
    )


def reference_planning() -> list[Concert]:
    """Planning de référence du 18/06.

    Iron Vow Mainstage 18h-19h, Crimson Engine Mainstage 19h30-20h30, Concrete Reign Warzone 17h-17h45.
    """
    return [
        concert(10, IRON_VOW, MAINSTAGE, slot(18, (18, 0), (19, 0))),
        concert(11, CRIMSON, MAINSTAGE, slot(18, (19, 30), (20, 30))),
        concert(12, CONCRETE, WARZONE, slot(18, (17, 0), (17, 45))),
    ]
