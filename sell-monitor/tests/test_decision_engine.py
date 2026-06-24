from __future__ import annotations

import unittest
from datetime import datetime

from sell_monitor.domain.enums import Action
from sell_monitor.domain.models import Signal
from sell_monitor.notifier.symbol_display import display_symbol, normalize_symbol_name
from sell_monitor.scoring.decision_engine import build_decision


class DecisionEngineTest(unittest.TestCase):
    def test_reduce_threshold_uses_report_time_price(self) -> None:
        decision = build_decision(
            "TEST",
            4,
            [Signal("x", 4, True, "reduce", trigger_price=12.34, triggered_at=datetime(2026, 6, 5, 10, 30))],
            symbol_name="测试股份",
            current_price=13.57,
        )
        self.assertEqual(decision.action, Action.REDUCE)
        self.assertEqual(decision.symbol_name, "测试股份")
        self.assertEqual(decision.current_price, 13.57)

    def test_exit_threshold_uses_report_time_price(self) -> None:
        decision = build_decision(
            "TEST",
            6,
            [Signal("x", 6, True, "exit", trigger_price=23.45, triggered_at=datetime(2026, 6, 5, 14, 0))],
            current_price=24.56,
        )
        self.assertEqual(decision.action, Action.EXIT_ALL)
        self.assertEqual(decision.current_price, 24.56)

    def test_falls_back_to_current_price_when_signal_price_missing(self) -> None:
        decision = build_decision(
            "TEST",
            4,
            [Signal("x", 4, True, "reduce")],
            current_price=15.67,
        )
        self.assertEqual(decision.current_price, 15.67)

    def test_does_not_replace_report_time_price_with_latest_signal_price(self) -> None:
        decision = build_decision(
            "TEST",
            6,
            [
                Signal("a", 1, True, "first", triggered_at=datetime(2026, 6, 5, 9, 30), trigger_price=10.01),
                Signal("b", 2, True, "second", triggered_at=datetime(2026, 6, 5, 10, 30), trigger_price=10.88),
            ],
            current_price=11.11,
        )
        self.assertEqual(decision.current_price, 11.11)

    def test_non_chinese_name_is_not_treated_as_stock_name(self) -> None:
        self.assertIsNone(normalize_symbol_name("TESTA", "Test A"))
        self.assertEqual("TESTA", display_symbol("TESTA", "Test A"))


if __name__ == "__main__":
    unittest.main()
