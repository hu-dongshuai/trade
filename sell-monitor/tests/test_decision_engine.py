from __future__ import annotations

import unittest

from sell_monitor.domain.enums import Action
from sell_monitor.domain.models import Signal
from sell_monitor.scoring.decision_engine import build_decision


class DecisionEngineTest(unittest.TestCase):
    def test_reduce_threshold(self) -> None:
        decision = build_decision("TEST", 4, [Signal("x", 4, True, "reduce")])
        self.assertEqual(decision.action, Action.REDUCE)

    def test_exit_threshold(self) -> None:
        decision = build_decision("TEST", 6, [Signal("x", 6, True, "exit")])
        self.assertEqual(decision.action, Action.EXIT_ALL)


if __name__ == "__main__":
    unittest.main()

