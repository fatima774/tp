"""Agrégat Artiste.

Un artiste existe indépendamment des festivals : il peut être programmé dans
plusieurs festivals. C'est donc un agrégat séparé, référencé par son identifiant
depuis les concerts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.value_objects import EquipmentSet, require_text


@dataclass(eq=False)
class Artist:
    id: int | None
    name: str
    genre: str
    required_equipment: EquipmentSet = field(default_factory=EquipmentSet)

    @classmethod
    def create(cls, name: str, genre: str, required_equipment: EquipmentSet) -> Artist:
        return cls(
            id=None,
            name=require_text(name, "Le nom de l'artiste", min_length=2, max_length=120),
            genre=require_text(genre, "Le genre", min_length=2, max_length=80),
            required_equipment=required_equipment,
        )
