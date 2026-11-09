"""Données de démonstration : `python -m app.seed`.

Attention : réinitialise complètement la base configurée.

Les données passent par les cas d'utilisation (et non par des INSERT directs) :
le jeu de données respecte donc forcément toutes les règles métier.
"""

from __future__ import annotations

from datetime import datetime

from app.application.use_cases.catalog import AddStageCommand, RegisterArtistCommand
from app.application.use_cases.concerts import ScheduleConcertCommand
from app.application.use_cases.festivals import CreateFestivalCommand
from app.bootstrap import build_container
from app.config import Settings

ARTISTS = [
    ("Iron Vow", "Heavy metal", ["large_rigging", "special_lighting"]),
    ("Crimson Engine", "Thrash metal", ["special_lighting"]),
    ("The Last Citadel", "Power metal", ["large_rigging"]),
    ("Concrete Reign", "Hardcore", []),
    ("Ashes of Tomorrow", "Metalcore", ["special_lighting"]),
    ("Static Violence", "Punk", []),
    ("Hollow Mountain", "Stoner", ["special_lighting"]),
    ("Solar Funeral", "Doom metal", []),
    ("Desert Crown", "Sludge", []),
    ("Winter Throne", "Black metal", ["special_lighting"]),
    ("Nocturnal Veil", "Black metal", []),
    ("Pale Kingdom", "Atmospheric metal", ["special_lighting"]),
]

STAGES = [
    ("Mainstage", 50000, ["large_rigging", "special_lighting", "pyrotechnics"]),
    ("Warzone", 15000, ["special_lighting"]),
    ("Valley", 8000, ["special_lighting"]),
    ("Temple", 10000, ["special_lighting"]),
]

SHOWS = [
    ("Iron Vow", "Mainstage", "2027-06-18T18:00:00", "2027-06-18T19:00:00"),
    ("Crimson Engine", "Mainstage", "2027-06-18T19:30:00", "2027-06-18T20:30:00"),
    ("The Last Citadel", "Mainstage", "2027-06-18T21:00:00", "2027-06-18T22:00:00"),
    ("Concrete Reign", "Warzone", "2027-06-18T17:00:00", "2027-06-18T17:45:00"),
    ("Ashes of Tomorrow", "Warzone", "2027-06-18T18:15:00", "2027-06-18T19:00:00"),
    ("Hollow Mountain", "Valley", "2027-06-18T19:00:00", "2027-06-18T20:00:00"),
    ("Solar Funeral", "Valley", "2027-06-18T20:30:00", "2027-06-18T21:30:00"),
    ("Winter Throne", "Temple", "2027-06-18T20:00:00", "2027-06-18T21:00:00"),
    ("Nocturnal Veil", "Temple", "2027-06-18T21:30:00", "2027-06-18T22:30:00"),
    ("Static Violence", "Warzone", "2027-06-19T14:00:00", "2027-06-19T14:45:00"),
    ("Desert Crown", "Valley", "2027-06-19T15:00:00", "2027-06-19T16:00:00"),
    ("Pale Kingdom", "Temple", "2027-06-19T16:30:00", "2027-06-19T17:30:00"),
    ("Iron Vow", "Mainstage", "2027-06-19T21:00:00", "2027-06-19T22:00:00"),
    ("Crimson Engine", "Mainstage", "2027-06-20T20:00:00", "2027-06-20T21:00:00"),
]


def seed(settings: Settings | None = None) -> None:
    c = build_container(settings)
    c.reset_schema()
    festival = c.create_festival().execute(
        CreateFestivalCommand(
            name="Hellforge Open Air",
            location="Clisson-sur-Rivière",
            start_date=datetime.fromisoformat("2027-06-18T10:00:00"),
            end_date=datetime.fromisoformat("2027-06-20T23:59:00"),
        )
    )
    artists = {
        name: c.register_artist().execute(RegisterArtistCommand(name, genre, equipment)).id
        for name, genre, equipment in ARTISTS
    }
    stages = {
        name: c.add_stage().execute(AddStageCommand(festival.id, name, capacity, equipment)).id
        for name, capacity, equipment in STAGES
    }
    for artist, stage, start, end in SHOWS:
        c.schedule_concert().execute(
            ScheduleConcertCommand(
                festival.id,
                artists[artist],
                stages[stage],
                datetime.fromisoformat(start),
                datetime.fromisoformat(end),
            )
        )
    c.engine.dispose()
    print(f"Données chargées : {festival.name}, {len(STAGES)} scènes, {len(ARTISTS)} artistes, {len(SHOWS)} concerts.")


if __name__ == "__main__":
    seed()
