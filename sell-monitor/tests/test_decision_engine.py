from __future__ import annotations

import unittest

from sell_monitor.domain.enums import Action
from sell_monitor.domain.models import Signal
from sell_monitor.notifier.symbol_display import display_symbol, normalize_symbol_name
from sell_monitor.scoring.decision_engine import build_decision


class DecisionEngineTest(unittest.TestCase):
    def test_reduce_threshold(self) -> None:
        decision = build_decision("TEST", 4, [Signal("x", 4, True, "reduce")], symbol_name="测试股份")
        self.assertEqual(decision.action, Action.REDUCE)
        self.assertEqual(decision.symbol_name, "测试股份")

    def test_exit_threshold(self) -> None:
        decision = build_decision("TEST", 6, [Signal("x", 6, True, "exit")])
        self.assertEqual(decision.action, Action.EXIT_ALL)

    def test_non_chinese_name_is_not_treated_as_stock_name(self) -> None:
        self.assertIsNone(normalize_symbol_name("TESTA", "Test A"))
        self.assertEqual("TESTA", display_symbol("TESTA", "Test A"))


if __name__ == "__main__":
    unittest.main()
