"""Transmission des événements de domaine au port de notification.

C'est ici qu'est corrigé le défaut 2.

Règle retenue : la notification est un EFFET SECONDAIRE. Elle est envoyée
après le commit ; si elle échoue, l'opération métier reste valide et le
résultat l'indique (`notification_status = "failed"`) au lieu de lever une
erreur 500. L'échec est journalisé pour que l'équipe puisse renvoyer le message.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from enum import Enum

from app.application.ports import Notifier
from app.domain.events import DomainEvent

logger = logging.getLogger("festiplan.notifications")


class NotificationStatus(str, Enum):
    NONE = "none"  # aucune notification à envoyer
    SENT = "sent"  # toutes les notifications sont parties
    FAILED = "failed"  # au moins une notification a échoué (l'opération est quand même enregistrée)


class EventDispatcher:
    def __init__(self, notifier: Notifier) -> None:
        self._notifier = notifier

    def dispatch(self, events: Iterable[DomainEvent]) -> NotificationStatus:
        events = list(events)
        if not events:
            return NotificationStatus.NONE
        status = NotificationStatus.SENT
        for event in events:
            try:
                self._notifier.notify(event)
            except Exception:  # noqa: BLE001 — aucune panne de notification ne doit annuler l'opération
                logger.exception(
                    "Notification non envoyée pour %s (l'opération est enregistrée)",
                    type(event).__name__,
                )
                status = NotificationStatus.FAILED
        return status
