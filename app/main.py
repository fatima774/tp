"""Point d'entrée de l'API : `uvicorn app.main:app --reload`.

`create_app` construit une application à partir d'une configuration ; les
tests l'appellent avec une base temporaire et un faux service de notification.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.inbound.http.errors import register_error_handlers
from app.adapters.inbound.http.routers import ALL_ROUTERS
from app.application.ports import Notifier
from app.bootstrap import build_container
from app.config import Settings

logging.basicConfig(level=logging.WARNING, format="%(levelname)s [%(name)s] %(message)s")


def create_app(settings: Settings | None = None, notifier: Notifier | None = None) -> FastAPI:
    container = build_container(settings, notifier)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Crée les tables au démarrage du serveur (et non plus à l'import du module).
        container.create_schema()
        yield
        container.engine.dispose()

    app = FastAPI(
        title=container.settings.app_name,
        version="1.0.0",
        description="API de gestion d'un festival fictif — version refactorisée (architecture hexagonale)",
        lifespan=lifespan,
    )
    app.state.container = container
    for router in ALL_ROUTERS:
        app.include_router(router)
    register_error_handlers(app)

    @app.get("/", tags=["health"])
    def health():
        return {"message": "Bienvenue sur FestiPlan", "status": "ok"}

    return app


app = create_app()
