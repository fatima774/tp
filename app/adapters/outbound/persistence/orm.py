"""Tables SQLAlchemy (adaptateur de persistance).

Ces classes décrivent les TABLES, pas le modèle métier. Le domaine ne les
importe jamais : la conversion se fait dans `repositories.py`.

Le schéma est identique à celui de la version initiale (mêmes tables, mêmes
colonnes) : une base existante reste lisible.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class FestivalRow(Base):
    __tablename__ = "festivals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="preparation", nullable=False)
    stages: Mapped[list[StageRow]] = relationship(back_populates="festival", order_by="StageRow.id")
    concerts: Mapped[list[ConcertRow]] = relationship(back_populates="festival", order_by="ConcertRow.id")


class ArtistRow(Base):
    __tablename__ = "artists"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    genre: Mapped[str] = mapped_column(String(80), nullable=False)
    required_equipment: Mapped[str] = mapped_column(Text, default="", nullable=False)


class StageRow(Base):
    __tablename__ = "stages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    festival_id: Mapped[int] = mapped_column(ForeignKey("festivals.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    available_equipment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    festival: Mapped[FestivalRow] = relationship(back_populates="stages")


class ConcertRow(Base):
    __tablename__ = "concerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    festival_id: Mapped[int] = mapped_column(ForeignKey("festivals.id"), nullable=False)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id"), nullable=False)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="scheduled", nullable=False)
    festival: Mapped[FestivalRow] = relationship(back_populates="concerts")


class IncidentRow(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    concert_id: Mapped[int] = mapped_column(ForeignKey("concerts.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
