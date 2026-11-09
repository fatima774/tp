"""Doubles de test : implémentations EN MÉMOIRE des ports.

Ils permettent de tester les cas d'utilisation sans SQLite ni FastAPI.
Les objets sont copiés (deepcopy) à la lecture et à l'écriture, comme une
vraie base : modifier un objet chargé ne change rien tant qu'il n'est pas
enregistré.
"""

from __future__ import annotations

import copy

from app.application.ports import NotificationError
from app.domain.artist import Artist
from app.domain.events import DomainEvent
from app.domain.festival import Festival
from app.domain.incident import Incident


class InMemoryFestivalRepository:
    def __init__(self) -> None:
        self.items: dict[int, Festival] = {}
        self.next_id = 1
        self.next_child_id = 100

    def get(self, festival_id):
        f = self.items.get(festival_id)
        return copy.deepcopy(f) if f else None

    def get_by_concert(self, concert_id):
        for f in self.items.values():
            if f.find_concert(concert_id):
                return copy.deepcopy(f)
        return None

    def list(self):
        return [copy.deepcopy(f) for f in self.items.values()]

    def add(self, festival):
        festival.id = self.next_id
        self.next_id += 1
        self.save(festival)

    def save(self, festival):
        for child in (*festival.stages, *festival.concerts):
            if child.id is None:
                child.id = self.next_child_id
                self.next_child_id += 1
        stored = copy.deepcopy(festival)
        stored.pull_events()
        self.items[festival.id] = stored


class InMemoryArtistRepository:
    def __init__(self) -> None:
        self.items: dict[int, Artist] = {}
        self.next_id = 1

    def get(self, artist_id):
        a = self.items.get(artist_id)
        return copy.deepcopy(a) if a else None

    def get_many(self, artist_ids):
        return {i: copy.deepcopy(self.items[i]) for i in artist_ids if i in self.items}

    def list(self):
        return sorted((copy.deepcopy(a) for a in self.items.values()), key=lambda a: a.name)

    def exists_with_name(self, name):
        return any(a.name == name for a in self.items.values())

    def add(self, artist):
        artist.id = self.next_id
        self.next_id += 1
        self.items[artist.id] = copy.deepcopy(artist)


class InMemoryIncidentRepository:
    def __init__(self) -> None:
        self.items: list[Incident] = []
        self.next_id = 1

    def add(self, incident):
        incident.id = self.next_id
        self.next_id += 1
        self.items.append(copy.deepcopy(incident))

    def list(self, concert_id=None):
        return [i for i in self.items if concert_id is None or i.concert_id == concert_id]


class FakeUnitOfWork:
    """Unité de travail en mémoire.

    Les écritures ne sont visibles qu'après `commit()` : on travaille sur une
    copie des repositories, recopiée dans l'état « commité » au commit.
    `commits` compte les validations pour vérifier qu'une erreur n'a rien enregistré.
    """

    def __init__(self) -> None:
        self._committed = (
            InMemoryFestivalRepository(),
            InMemoryArtistRepository(),
            InMemoryIncidentRepository(),
        )
        self.commits = 0

    def __enter__(self):
        self.festivals, self.artists, self.incidents = copy.deepcopy(self._committed)
        return self

    def __exit__(self, *args):
        self.rollback()

    def commit(self):
        self._committed = copy.deepcopy((self.festivals, self.artists, self.incidents))
        self.commits += 1

    def rollback(self):
        pass  # les copies de travail sont simplement abandonnées

    # accès direct à l'état commité, pour préparer et vérifier les tests
    @property
    def stored_festivals(self) -> InMemoryFestivalRepository:
        return self._committed[0]

    @property
    def stored_artists(self) -> InMemoryArtistRepository:
        return self._committed[1]

    @property
    def stored_incidents(self) -> InMemoryIncidentRepository:
        return self._committed[2]


class RecordingNotifier:
    """Faux notifier : enregistre les événements reçus, peut simuler une panne."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[DomainEvent] = []

    def notify(self, event: DomainEvent) -> None:
        if self.fail:
            raise NotificationError("panne simulée")
        self.events.append(event)
