"""Ports sortants : les contrats dont le cœur de l'application a besoin.

Un port est une interface (ici un `Protocol` Python). Les cas d'utilisation
dépendent de ces contrats, jamais de SQLAlchemy ou d'un service d'e-mail.
Les implémentations concrètes (les adaptateurs) sont dans `app/adapters/outbound`,
et les tests utilisent des implémentations en mémoire (`tests/fakes.py`).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.domain.artist import Artist
from app.domain.events import DomainEvent
from app.domain.festival import Festival
from app.domain.incident import Incident


class FestivalRepository(Protocol):
    """Charge et enregistre l'agrégat Festival en entier (scènes et concerts compris)."""

    def get(self, festival_id: int) -> Festival | None: ...

    def get_by_concert(self, concert_id: int) -> Festival | None: ...

    def list(self) -> list[Festival]: ...

    def add(self, festival: Festival) -> None: ...

    def save(self, festival: Festival) -> None: ...


class ArtistRepository(Protocol):
    def get(self, artist_id: int) -> Artist | None: ...

    def get_many(self, artist_ids: Iterable[int]) -> dict[int, Artist]: ...

    def list(self) -> list[Artist]: ...

    def exists_with_name(self, name: str) -> bool: ...

    def add(self, artist: Artist) -> None: ...


class IncidentRepository(Protocol):
    def add(self, incident: Incident) -> None: ...

    def list(self, concert_id: int | None = None) -> list[Incident]: ...


class UnitOfWork(Protocol):
    """Unité de travail : regroupe les repositories et décide du commit.

    Dans la version initiale, chaque repository faisait son propre commit.
    Ici, c'est le cas d'utilisation qui décide quand l'opération est validée :
    soit tout est enregistré, soit rien.

    Usage :
        with uow:
            ...
            uow.commit()
    En sortie du bloc `with`, tout ce qui n'a pas été commité est annulé.
    """

    festivals: FestivalRepository
    artists: ArtistRepository
    incidents: IncidentRepository

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(self, *args: object) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class NotificationError(Exception):
    """Levée par un adaptateur de notification quand l'envoi échoue."""


class Notifier(Protocol):
    """Port de notification : réagit à un événement de domaine."""

    def notify(self, event: DomainEvent) -> None: ...
