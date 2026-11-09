import pytest

from app.adapters.outbound.notifications.fake_email import FakeEmailNotifier
from app.application.ports import NotificationError
from app.domain.events import ConcertRescheduled
from tests.builders import slot

EVENT = ConcertRescheduled(
    festival_id=1, concert_id=2, previous_slot=slot(18, (19, 30), (20, 30)), new_slot=slot(18, (22, 0), (23, 0))
)


def test_fake_email_prints_message(capsys):
    FakeEmailNotifier().notify(EVENT)
    out = capsys.readouterr().out
    assert "Modification du concert #2" in out and "[FAKE EMAIL]" in out


def test_fake_email_can_simulate_failure():
    with pytest.raises(NotificationError):
        FakeEmailNotifier(fail=True).notify(EVENT)
