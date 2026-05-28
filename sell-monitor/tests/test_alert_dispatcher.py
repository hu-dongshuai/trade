from __future__ import annotations

import unittest

from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Decision
from sell_monitor.notifier.alert_dispatcher import ConsoleAlertDispatcher


class _FakeChannel:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, subject: str, message: str) -> None:
        self.messages.append((subject, message))


class AlertDispatcherTest(unittest.TestCase):
    def test_dispatch_builds_subject_and_message(self) -> None:
        channel = _FakeChannel()
        dispatcher = ConsoleAlertDispatcher(channels=[channel], subject_prefix="[Test]")
        decision = Decision(
            symbol="TESTA",
            action=Action.REDUCE,
            total_score=4,
            priority=Priority.HIGH,
            reasons=["15分钟出现危险上影线"],
            next_step="减仓",
            cancel_condition="信号消失",
        )

        dispatcher.dispatch(decision)

        self.assertEqual(1, len(channel.messages))
        subject, message = channel.messages[0]
        self.assertIn("[Test] TESTA reduce score=4", subject)
        self.assertIn("15分钟出现危险上影线", message)
