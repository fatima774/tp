"""Cas d'utilisation « catalogue » : artistes et scènes."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.dto import ArtistView, StageView
from app.application.errors import AlreadyExistsError, InvalidReferenceError
from app.application.ports import UnitOfWork
from app.application.use_cases.festivals import load_festival
from app.domain.artist import Artist
from app.domain.value_objects import Capacity, EquipmentSet


@dataclass(frozen=True)
class RegisterArtistCommand:
    name: str
    genre: str
    required_equipment: list[str] = field(default_factory=list)


class RegisterArtist:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, cmd: RegisterArtistCommand) -> ArtistView:
        artist = Artist.create(cmd.name, cmd.genre, EquipmentSet.of(cmd.required_equipment))
        with self.uow:
            if self.uow.artists.exists_with_name(artist.name):
                raise AlreadyExistsError(f"Un artiste nommé « {artist.name} » existe déjà")
            self.uow.artists.add(artist)
            self.uow.commit()
        return ArtistView.of(artist)


class ListArtists:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self) -> list[ArtistView]:
        with self.uow:
            return [ArtistView.of(a) for a in self.uow.artists.list()]


@dataclass(frozen=True)
class AddStageCommand:
    festival_id: int
    name: str
    capacity: int
    available_equipment: list[str] = field(default_factory=list)


class AddStage:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, cmd: AddStageCommand) -> StageView:
        capacity = Capacity(cmd.capacity)  # R9, vérifiée même sans passer par HTTP
        equipment = EquipmentSet.of(cmd.available_equipment)
        with self.uow:
            festival = self.uow.festivals.get(cmd.festival_id)
            if festival is None:
                raise InvalidReferenceError("Festival introuvable", rule="R4")
            stage = festival.add_stage(cmd.name, capacity, equipment)
            self.uow.festivals.save(festival)
            self.uow.commit()
        return StageView.of(festival, stage)


class ListStages:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def execute(self, festival_id: int) -> list[StageView]:
        with self.uow:
            festival = load_festival(self.uow, festival_id)
            return [StageView.of(festival, s) for s in festival.stages]
