"""Fixtures partagées.

Les tests du domaine et de l'application n'utilisent aucune de ces fixtures.
Les tests d'adaptateurs et de non-régression utilisent une base SQLite
temporaire (une par test) et un faux notifier qu'on peut mettre en panne.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.seed import seed
from tests.fakes import RecordingNotifier


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def notifier():
    return RecordingNotifier()


@pytest.fixture
def client(settings, notifier):
    """API sur une base vide."""
    with TestClient(create_app(settings, notifier)) as c:
        yield c


@pytest.fixture
def seeded_client(settings, notifier, capsys):
    """API sur le jeu de données de démonstration (Hellforge Open Air)."""
    seed(settings)
    capsys.readouterr()
    with TestClient(create_app(settings, notifier)) as c:
        yield c
