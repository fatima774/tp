"""Contrôleurs HTTP (adaptateur entrant).

Un contrôleur fait trois choses seulement :
  1. recevoir la requête validée par Pydantic ;
  2. la transformer en commande et appeler LE cas d'utilisation correspondant ;
  3. transformer le résultat en réponse.
Aucune règle métier, aucun accès à la base ici.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.adapters.inbound.http.dependencies import get_container
from app.adapters.inbound.http.schemas import (
    ArtistCreate,
    ArtistRead,
    ConcertChangeRead,
    ConcertCreate,
    ConcertRead,
    ConcertReschedule,
    ErrorRead,
    FestivalChangeRead,
    FestivalCreate,
    FestivalRead,
    IncidentCreate,
    IncidentRead,
    StageCreate,
    StageRead,
)
from app.application.dto import ConcertChange, FestivalChange
from app.application.use_cases.catalog import AddStageCommand, RegisterArtistCommand
from app.application.use_cases.concerts import RescheduleConcertCommand, ScheduleConcertCommand
from app.application.use_cases.festivals import CreateFestivalCommand
from app.application.use_cases.incidents import ReportIncidentCommand
from app.bootstrap import Container

ERRORS = {400: {"model": ErrorRead}, 404: {"model": ErrorRead}, 409: {"model": ErrorRead}}


def concert_change(result: ConcertChange) -> dict:
    return {**asdict(result.concert), "notification_status": result.notification_status.value}


def festival_change(result: FestivalChange) -> dict:
    return {**asdict(result.festival), "notification_status": result.notification_status.value}


# ---------------------------------------------------------------- festivals
festivals = APIRouter(prefix="/festivals", tags=["festivals"], responses=ERRORS)


@festivals.get("", response_model=list[FestivalRead])
def list_festivals(c: Container = Depends(get_container)):
    return c.list_festivals().execute()


@festivals.post("", response_model=FestivalRead, status_code=201)
def create_festival(payload: FestivalCreate, c: Container = Depends(get_container)):
    return c.create_festival().execute(CreateFestivalCommand(**payload.model_dump()))


@festivals.get("/{festival_id}", response_model=FestivalRead)
def get_festival(festival_id: int, c: Container = Depends(get_container)):
    return c.get_festival().execute(festival_id)


@festivals.post("/{festival_id}/publish", response_model=FestivalChangeRead)
def publish_festival(festival_id: int, c: Container = Depends(get_container)):
    """Publie le planning si ses concerts respectent les règles de programmation (R8)."""
    return festival_change(c.publish_planning().execute(festival_id))


@festivals.post("/{festival_id}/unpublish", response_model=FestivalChangeRead)
def unpublish_festival(festival_id: int, c: Container = Depends(get_container)):
    """Procédure explicite (R7) : repasse le planning en préparation pour pouvoir le modifier."""
    return festival_change(c.unpublish_planning().execute(festival_id))


# ---------------------------------------------------------------- artistes
artists = APIRouter(prefix="/artists", tags=["artists"], responses=ERRORS)


@artists.get("", response_model=list[ArtistRead])
def list_artists(c: Container = Depends(get_container)):
    return c.list_artists().execute()


@artists.post("", response_model=ArtistRead, status_code=201)
def create_artist(payload: ArtistCreate, c: Container = Depends(get_container)):
    return c.register_artist().execute(RegisterArtistCommand(**payload.model_dump()))


# ---------------------------------------------------------------- scènes
stages = APIRouter(prefix="/stages", tags=["stages"], responses=ERRORS)


@stages.get("", response_model=list[StageRead])
def list_stages(festival_id: int, c: Container = Depends(get_container)):
    return c.list_stages().execute(festival_id)


@stages.post("", response_model=StageRead, status_code=201)
def create_stage(payload: StageCreate, c: Container = Depends(get_container)):
    return c.add_stage().execute(AddStageCommand(**payload.model_dump()))


# ---------------------------------------------------------------- concerts
concerts = APIRouter(prefix="/concerts", tags=["concerts"], responses=ERRORS)


@concerts.get("", response_model=list[ConcertRead])
def list_concerts(festival_id: int, c: Container = Depends(get_container)):
    return c.get_planning().execute(festival_id)


@concerts.get("/schedule/{festival_id}", response_model=list[ConcertRead])
def get_schedule(festival_id: int, c: Container = Depends(get_container)):
    """Planning d'un festival dans l'ordre chronologique."""
    return c.get_planning().execute(festival_id)


@concerts.get("/{concert_id}", response_model=ConcertRead)
def get_concert(concert_id: int, c: Container = Depends(get_container)):
    return c.get_concert().execute(concert_id)


@concerts.post("", response_model=ConcertRead, status_code=201)
def create_concert(payload: ConcertCreate, c: Container = Depends(get_container)):
    return c.schedule_concert().execute(ScheduleConcertCommand(**payload.model_dump()))


@concerts.patch("/{concert_id}/reschedule", response_model=ConcertChangeRead)
def reschedule_concert(
    concert_id: int, payload: ConcertReschedule, c: Container = Depends(get_container)
):
    cmd = RescheduleConcertCommand(concert_id, payload.start_time, payload.end_time)
    return concert_change(c.reschedule_concert().execute(cmd))


@concerts.post("/{concert_id}/cancel", response_model=ConcertChangeRead)
def cancel_concert(concert_id: int, c: Container = Depends(get_container)):
    return concert_change(c.cancel_concert().execute(concert_id))


# ---------------------------------------------------------------- incidents
incidents = APIRouter(prefix="/incidents", tags=["incidents"], responses=ERRORS)


@incidents.post("", response_model=IncidentRead, status_code=201)
def create_incident(payload: IncidentCreate, c: Container = Depends(get_container)):
    return c.report_incident().execute(ReportIncidentCommand(**payload.model_dump()))


@incidents.get("", response_model=list[IncidentRead])
def list_incidents(concert_id: int | None = None, c: Container = Depends(get_container)):
    return c.list_incidents().execute(concert_id)


ALL_ROUTERS = (festivals, artists, stages, concerts, incidents)
