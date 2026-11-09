"""Implémentations SQLAlchemy des ports de repository.

Rôle : traduire entre les lignes de tables (orm.py) et les objets métier.
Les repositories ne commitent JAMAIS : ils font au plus un `flush` pour
obtenir les identifiants générés. Le commit est décidé par l'unité de travail.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adapters.outbound.persistence.orm import (
    ArtistRow,
    ConcertRow,
    FestivalRow,
    IncidentRow,
    StageRow,
)
from app.domain.artist import Artist
from app.domain.festival import Concert, ConcertStatus, Festival, FestivalStatus, Stage
from app.domain.incident import Incident
from app.domain.value_objects import Capacity, EquipmentSet, FestivalPeriod, TimeSlot

# ---------------------------------------------------------------- équipements


def encode_equipment(equipment: EquipmentSet) -> str:
    """Stocké en JSON : un nom d'équipement peut contenir une virgule sans être découpé."""
    return json.dumps(equipment.as_sorted_list(), ensure_ascii=False)


def decode_equipment(raw: str | None) -> EquipmentSet:
    """Lit le JSON, ou l'ancien format « a,b,c » des bases créées par la version initiale."""
    raw = (raw or "").strip()
    if not raw:
        return EquipmentSet()
    if raw.startswith("["):
        return EquipmentSet.of(json.loads(raw))
    return EquipmentSet.of(x.strip() for x in raw.split(",") if x.strip())


# ---------------------------------------------------------------- festivals


class SqlAlchemyFestivalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _query(self):
        return select(FestivalRow).options(selectinload(FestivalRow.stages), selectinload(FestivalRow.concerts))

    def get(self, festival_id: int) -> Festival | None:
        row = self.session.scalars(self._query().where(FestivalRow.id == festival_id)).first()
        return self._to_domain(row) if row else None

    def get_by_concert(self, concert_id: int) -> Festival | None:
        festival_id = self.session.scalar(select(ConcertRow.festival_id).where(ConcertRow.id == concert_id))
        return self.get(festival_id) if festival_id is not None else None

    def list(self) -> list[Festival]:
        rows = self.session.scalars(self._query().order_by(FestivalRow.id)).all()
        return [self._to_domain(r) for r in rows]

    def add(self, festival: Festival) -> None:
        row = FestivalRow()
        self._copy_festival(festival, row)
        self.session.add(row)
        self.session.flush()
        festival.id = row.id
        self._sync_children(festival, row)

    def save(self, festival: Festival) -> None:
        row = self.session.get(FestivalRow, festival.id)
        if row is None:  # pragma: no cover — un agrégat chargé existe forcément
            raise LookupError(f"Festival #{festival.id} absent de la base")
        self._copy_festival(festival, row)
        self._sync_children(festival, row)

    # -- conversions

    @staticmethod
    def _copy_festival(festival: Festival, row: FestivalRow) -> None:
        row.name = festival.name
        row.location = festival.location
        row.start_date = festival.period.start
        row.end_date = festival.period.end
        row.status = festival.status.value

    def _sync_children(self, festival: Festival, row: FestivalRow) -> None:
        """Répercute les scènes et concerts de l'agrégat dans les tables.

        Les objets nouveaux (id = None) donnent une nouvelle ligne ; après le
        `flush`, on recopie l'identifiant généré par la base dans l'objet métier.
        """
        created: list[tuple[Stage | Concert, StageRow | ConcertRow]] = []

        stage_rows = {s.id: s for s in row.stages}
        for stage in festival.stages:
            srow = stage_rows.get(stage.id)
            if srow is None:
                srow = StageRow()
                row.stages.append(srow)
                created.append((stage, srow))
            srow.name = stage.name
            srow.capacity = stage.capacity.value
            srow.available_equipment = encode_equipment(stage.equipment)

        concert_rows = {c.id: c for c in row.concerts}
        for concert in festival.concerts:
            crow = concert_rows.get(concert.id)
            if crow is None:
                crow = ConcertRow()
                row.concerts.append(crow)
                created.append((concert, crow))
            crow.artist_id = concert.artist_id
            crow.stage_id = concert.stage_id
            crow.start_time = concert.slot.start
            crow.end_time = concert.slot.end
            crow.status = concert.status.value

        self.session.flush()
        for obj, new_row in created:
            obj.id = new_row.id

    @staticmethod
    def _to_domain(row: FestivalRow) -> Festival:
        return Festival(
            id=row.id,
            name=row.name,
            location=row.location,
            period=FestivalPeriod(row.start_date, row.end_date),
            status=FestivalStatus(row.status),
            stages=[
                Stage(
                    id=s.id,
                    name=s.name,
                    capacity=Capacity(s.capacity),
                    equipment=decode_equipment(s.available_equipment),
                )
                for s in row.stages
            ],
            concerts=[
                Concert(
                    id=c.id,
                    artist_id=c.artist_id,
                    stage_id=c.stage_id,
                    slot=TimeSlot(c.start_time, c.end_time),
                    status=ConcertStatus(c.status),
                )
                for c in row.concerts
            ],
        )


# ---------------------------------------------------------------- artistes


class SqlAlchemyArtistRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, artist_id: int) -> Artist | None:
        row = self.session.get(ArtistRow, artist_id)
        return self._to_domain(row) if row else None

    def get_many(self, artist_ids: Iterable[int]) -> dict[int, Artist]:
        ids = list(artist_ids)
        if not ids:
            return {}
        rows = self.session.scalars(select(ArtistRow).where(ArtistRow.id.in_(ids))).all()
        return {r.id: self._to_domain(r) for r in rows}

    def list(self) -> list[Artist]:
        rows = self.session.scalars(select(ArtistRow).order_by(ArtistRow.name)).all()
        return [self._to_domain(r) for r in rows]

    def exists_with_name(self, name: str) -> bool:
        return self.session.scalar(select(ArtistRow.id).where(ArtistRow.name == name)) is not None

    def add(self, artist: Artist) -> None:
        row = ArtistRow(
            name=artist.name,
            genre=artist.genre,
            required_equipment=encode_equipment(artist.required_equipment),
        )
        self.session.add(row)
        self.session.flush()
        artist.id = row.id

    @staticmethod
    def _to_domain(row: ArtistRow) -> Artist:
        return Artist(
            id=row.id,
            name=row.name,
            genre=row.genre,
            required_equipment=decode_equipment(row.required_equipment),
        )


# ---------------------------------------------------------------- incidents


class SqlAlchemyIncidentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, incident: Incident) -> None:
        row = IncidentRow(
            concert_id=incident.concert_id,
            description=incident.description,
            occurred_at=incident.occurred_at,
            resolved=incident.resolved,
        )
        self.session.add(row)
        self.session.flush()
        incident.id = row.id

    def list(self, concert_id: int | None = None) -> list[Incident]:
        query = select(IncidentRow)
        if concert_id is not None:
            query = query.where(IncidentRow.concert_id == concert_id)
        rows = self.session.scalars(query.order_by(IncidentRow.occurred_at.desc())).all()
        return [Incident(r.id, r.concert_id, r.description, r.occurred_at, r.resolved) for r in rows]
