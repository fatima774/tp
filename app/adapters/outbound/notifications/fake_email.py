"""Adaptateur de notification : faux envoi d'e-mail (aucun e-mail réel n'est envoyé).

C'est le seul endroit qui sait qu'une notification est un « e-mail ».
Pour brancher un vrai service (SMTP, Slack...), il suffit d'écrire un autre
adaptateur qui respecte le port `Notifier`, sans toucher au domaine.
"""

from __future__ import annotations

import logging

from app.application.ports import NotificationError
from app.domain.events import (
    ConcertCancelled,
    ConcertRescheduled,
    DomainEvent,
    PlanningPublished,
    PlanningUnpublished,
)

logger = logging.getLogger("festiplan.email")


def describe(event: DomainEvent) -> tuple[str, str]:
    """Transforme un événement de domaine en (sujet, message)."""
    if isinstance(event, ConcertRescheduled):
        return (
            f"Modification du concert #{event.concert_id}",
            f"Concert déplacé : {event.previous_slot} -> {event.new_slot}",
        )
    if isinstance(event, ConcertCancelled):
        return (f"Annulation du concert #{event.concert_id}", "Le concert a été annulé.")
    if isinstance(event, PlanningPublished):
        return (
            f"Publication du festival #{event.festival_id}",
            f"Le planning du festival {event.festival_name} a été publié.",
        )
    if isinstance(event, PlanningUnpublished):
        return (
            f"Dépublication du festival #{event.festival_id}",
            f"Le planning du festival {event.festival_name} est repassé en préparation.",
        )
    return (type(event).__name__, repr(event))


class FakeEmailNotifier:
    def __init__(self, recipient: str = "production@festiplan.test", fail: bool = False) -> None:
        self.recipient = recipient
        self.fail = fail  # simule une panne du service (FESTIPLAN_FAIL_NOTIFICATIONS=true)

    def notify(self, event: DomainEvent) -> None:
        subject, body = describe(event)
        if self.fail:
            raise NotificationError("Simulation : le service de notification est indisponible")
        print(f"[FAKE EMAIL] to={self.recipient} subject={subject} body={body}")
