"""Schémas Pydantic : format des requêtes et réponses HTTP.

Pydantic vérifie le FORMAT (types, champs obligatoires, longueurs).
Les règles MÉTIER (R1 à R10) restent dans le domaine : elles s'appliquent
même si on appelle les cas d'utilisation sans passer par HTTP.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FestivalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    location: str = Field(min_length=2, max_length=120)
    start_date: datetime
    end_date: datetime


class FestivalRead(ReadModel):
    id: int
    name: str
    location: str
    start_date: datetime
    end_date: datetime
    status: str


class FestivalChangeRead(FestivalRead):
    notification_status: str = Field(description="none | sent | failed — un échec n'annule pas l'opération")


class ArtistCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    genre: str = Field(min_length=2, max_length=80)
    required_equipment: list[str] = []


class ArtistRead(ReadModel):
    id: int
    name: str
    genre: str
    required_equipment: list[str]


class StageCreate(BaseModel):
    festival_id: int
    name: str = Field(min_length=2, max_length=100)
    capacity: int = Field(gt=0)
    available_equipment: list[str] = []


class StageRead(ReadModel):
    id: int
    festival_id: int
    name: str
    capacity: int
    available_equipment: list[str]


class ConcertCreate(BaseModel):
    festival_id: int
    artist_id: int
    stage_id: int
    start_time: datetime
    end_time: datetime


class ConcertReschedule(BaseModel):
    start_time: datetime
    end_time: datetime


class ConcertRead(ReadModel):
    id: int
    festival_id: int
    artist_id: int
    stage_id: int
    start_time: datetime
    end_time: datetime
    status: str


class ConcertChangeRead(ConcertRead):
    notification_status: str = Field(description="none | sent | failed — un échec n'annule pas l'opération")


class IncidentCreate(BaseModel):
    concert_id: int
    description: str = Field(min_length=3, max_length=2000)
    occurred_at: datetime | None = None


class IncidentRead(ReadModel):
    id: int
    concert_id: int
    description: str
    occurred_at: datetime
    resolved: bool


class ErrorRead(BaseModel):
    detail: str
    rule: str | None = None
    violations: list[str] | None = None
