"""Traduction des erreurs métier en réponses HTTP.

Avant : chaque contrôleur faisait son propre `try/except ValueError -> 400`
et `RuntimeError -> 500`. Maintenant la correspondance est définie une fois.

Codes retenus :
- 400 : donnée invalide ou référence inexistante dans le corps de la requête ;
- 404 : ressource de l'URL introuvable ;
- 409 : la demande est valide mais entre en conflit avec l'état actuel
        (chevauchement, planning publié, transition interdite, doublon).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.application.errors import (
    AlreadyExistsError,
    ApplicationError,
    InvalidReferenceError,
    NotFoundError,
)
from app.domain.errors import (
    DomainError,
    InvalidStatusTransitionError,
    PlanningLockedError,
    PlanningNotPublishableError,
    SchedulingConflictError,
)

STATUS_BY_ERROR: list[tuple[type[Exception], int]] = [
    (NotFoundError, 404),
    (AlreadyExistsError, 409),
    (InvalidReferenceError, 400),
    (SchedulingConflictError, 409),
    (PlanningLockedError, 409),
    (InvalidStatusTransitionError, 409),
    (PlanningNotPublishableError, 409),
    (DomainError, 400),
]


def status_for(exc: Exception) -> int:
    for error_type, status in STATUS_BY_ERROR:
        if isinstance(exc, error_type):
            return status
    return 500


async def handle_business_error(_: Request, exc: Exception) -> JSONResponse:
    body: dict = {"detail": str(exc)}
    rule = getattr(exc, "rule", None)
    if rule:
        body["rule"] = rule
    if isinstance(exc, PlanningNotPublishableError):
        body["violations"] = exc.violations
    return JSONResponse(status_code=status_for(exc), content=body)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_business_error)
    app.add_exception_handler(ApplicationError, handle_business_error)
