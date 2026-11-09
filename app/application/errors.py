"""Erreurs de la couche application (ressource absente, doublon...).

Elles ne sont pas des règles du domaine : elles viennent du fait de chercher
des données qui n'existent pas.
"""


class ApplicationError(Exception):
    rule: str | None = None

    def __init__(self, message: str, rule: str | None = None) -> None:
        super().__init__(message)
        if rule is not None:
            self.rule = rule


class NotFoundError(ApplicationError):
    """La ressource désignée dans l'URL n'existe pas."""


class InvalidReferenceError(ApplicationError):
    """Le corps de la requête référence un festival, un artiste, une scène ou un concert inexistant (R4, R10)."""


class AlreadyExistsError(ApplicationError):
    """Une ressource portant ce nom existe déjà."""
