from fastapi import Request

from app.bootstrap import Container


def get_container(request: Request) -> Container:
    """Récupère le conteneur de dépendances attaché à l'application FastAPI."""
    return request.app.state.container
