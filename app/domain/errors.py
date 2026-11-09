"""Erreurs métier.

Le domaine signale qu'une règle est violée en levant une de ces exceptions.
Il ne connaît PAS les codes HTTP : c'est l'adaptateur HTTP qui traduit
chaque type d'erreur en réponse (400, 409...).

Chaque erreur peut porter la référence de la règle du sujet (R1 à R10),
ce qui rend les réponses de l'API et les tests plus faciles à relier au cahier des charges.
"""


class DomainError(Exception):
    """Base commune à toutes les violations de règles métier."""

    rule: str | None = None

    def __init__(self, message: str, rule: str | None = None) -> None:
        super().__init__(message)
        if rule is not None:
            self.rule = rule

    @property
    def message(self) -> str:
        return str(self)


class InvalidValueError(DomainError):
    """Valeur invalide : créneau incohérent (R1), capacité nulle (R9), texte vide (R10)..."""


class StageNotInFestivalError(DomainError):
    """La scène demandée n'appartient pas au festival du concert (R4)."""

    rule = "R4"


class MissingEquipmentError(DomainError):
    """La scène ne fournit pas les équipements requis par l'artiste (R5)."""

    rule = "R5"


class OutsideFestivalPeriodError(DomainError):
    """Le concert ne se déroule pas entièrement pendant le festival (R6)."""

    rule = "R6"


class SchedulingConflictError(DomainError):
    """Chevauchement sur une scène (R2) ou pour un artiste (R3)."""


class PlanningLockedError(DomainError):
    """Le planning est publié : les opérations ordinaires sont interdites (R7)."""

    rule = "R7"


class InvalidStatusTransitionError(DomainError):
    """Changement d'état non autorisé (publier deux fois, annuler un concert déjà annulé...)."""


class PlanningNotPublishableError(DomainError):
    """Le planning ne respecte pas les règles de programmation (R8)."""

    rule = "R8"

    def __init__(self, violations: list[str]) -> None:
        super().__init__("Le planning ne peut pas être publié : il ne respecte pas les règles de programmation")
        self.violations = violations
