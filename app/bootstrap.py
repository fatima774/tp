"""Module de composition (« composition root »).

C'est le SEUL endroit où les implémentations concrètes sont choisies et
assemblées : base SQLAlchemy, adaptateur de notification, cas d'utilisation.
Les cas d'utilisation reçoivent leurs dépendances ; ils ne les créent jamais.

Pour changer de base ou de système de notification, on ne modifie que ce fichier.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.outbound.notifications.fake_email import FakeEmailNotifier
from app.adapters.outbound.persistence.orm import Base
from app.adapters.outbound.persistence.unit_of_work import (
    SqlAlchemyUnitOfWork,
    build_engine,
    build_session_factory,
)
from app.application.events import EventDispatcher
from app.application.ports import Notifier
from app.application.use_cases.catalog import AddStage, ListArtists, ListStages, RegisterArtist
from app.application.use_cases.concerts import (
    CancelConcert,
    GetConcert,
    GetPlanning,
    RescheduleConcert,
    ScheduleConcert,
)
from app.application.use_cases.festivals import (
    CreateFestival,
    GetFestival,
    ListFestivals,
    PublishPlanning,
    UnpublishPlanning,
)
from app.application.use_cases.incidents import ListIncidents, ReportIncident
from app.config import Settings


@dataclass
class Container:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    notifier: Notifier

    # -- infrastructure
    def uow(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.session_factory)

    def dispatcher(self) -> EventDispatcher:
        return EventDispatcher(self.notifier)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def reset_schema(self) -> None:
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    # -- cas d'utilisation (une nouvelle instance par appel = une transaction)
    def create_festival(self):
        return CreateFestival(self.uow())

    def list_festivals(self):
        return ListFestivals(self.uow())

    def get_festival(self):
        return GetFestival(self.uow())

    def publish_planning(self):
        return PublishPlanning(self.uow(), self.dispatcher())

    def unpublish_planning(self):
        return UnpublishPlanning(self.uow(), self.dispatcher())

    def register_artist(self):
        return RegisterArtist(self.uow())

    def list_artists(self):
        return ListArtists(self.uow())

    def add_stage(self):
        return AddStage(self.uow())

    def list_stages(self):
        return ListStages(self.uow())

    def schedule_concert(self):
        return ScheduleConcert(self.uow())

    def reschedule_concert(self):
        return RescheduleConcert(self.uow(), self.dispatcher())

    def cancel_concert(self):
        return CancelConcert(self.uow(), self.dispatcher())

    def get_concert(self):
        return GetConcert(self.uow())

    def get_planning(self):
        return GetPlanning(self.uow())

    def report_incident(self):
        return ReportIncident(self.uow())

    def list_incidents(self):
        return ListIncidents(self.uow())


def build_container(settings: Settings | None = None, notifier: Notifier | None = None) -> Container:
    settings = settings or Settings()
    engine = build_engine(settings.database_url)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=build_session_factory(engine),
        notifier=notifier or FakeEmailNotifier(fail=settings.fail_notifications),
    )
