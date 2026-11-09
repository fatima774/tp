"""Agrégat Incident.

Un incident est déclaré pendant le festival, souvent par une autre personne que
celle qui gère le planning. Le placer dans l'agrégat Festival obligerait à
verrouiller tout le planning pour enregistrer un simple incident : on en fait
donc un agrégat à part, qui référence le concert par son identifiant.

R10 a deux parties :
- « description non vide » : vérifiée ici, dans l'objet métier ;
- « concert existant » : demande un accès aux données, donc vérifiée par le
  cas d'utilisation via le repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.value_objects import ensure_naive, require_text


@dataclass(eq=False)
class Incident:
    id: int | None
    concert_id: int
    description: str
    occurred_at: datetime
    resolved: bool = False

    @classmethod
    def report(cls, concert_id: int, description: str, occurred_at: datetime) -> Incident:
        ensure_naive(occurred_at)
        return cls(
            id=None,
            concert_id=concert_id,
            description=require_text(
                description, "La description de l'incident", max_length=2000, rule="R10"
            ),
            occurred_at=occurred_at,
        )
