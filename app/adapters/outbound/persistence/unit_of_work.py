"""Connexion à la base et unité de travail SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.outbound.persistence.repositories import (
    SqlAlchemyArtistRepository,
    SqlAlchemyFestivalRepository,
    SqlAlchemyIncidentRepository,
)


def build_engine(database_url: str) -> Engine:
    args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=args)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class SqlAlchemyUnitOfWork:
    """Implémentation du port UnitOfWork : une session SQLAlchemy = une transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self.session = self._session_factory()
        self.festivals = SqlAlchemyFestivalRepository(self.session)
        self.artists = SqlAlchemyArtistRepository(self.session)
        self.incidents = SqlAlchemyIncidentRepository(self.session)
        return self

    def __exit__(self, *args: object) -> None:
        # Tout ce qui n'a pas été commité explicitement est annulé (y compris en cas d'erreur métier).
        self.rollback()
        self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
