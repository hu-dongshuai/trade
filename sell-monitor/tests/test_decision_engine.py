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
            [Signal("second_dangerous_upper_wick", 4, True, "reduce", trigger_price=12.34, triggered_at=datetime(2026, 6, 5, 10, 30))],
            symbol_name="测试股份",
            current_price=13.57,
        )
        self.assertEqual(decision.action, Action.REDUCE)
        self.assertEqual(decision.symbol_name, "测试股份")
        self.assertEqual(decision.current_price, 13.57)

    def test_exit_requires_two_confirmation_dimensions(self) -> None:
        decision = build_decision(
            "TEST",
            6,
            [
                Signal("third_dangerous_upper_wick", 3, True, "third wick", trigger_price=23.45, triggered_at=datetime(2026, 6, 5, 14, 0)),
                Signal("structure_break", 2, True, "structure break"),
                Signal("m15_ma20_high_volume_break", 2, True, "ma20 break"),
            ],
            current_price=24.56,
        )
        self.assertEqual(decision.action, Action.EXIT_ALL)
        self.assertEqual(decision.current_price, 24.56)

    def test_exit_downgrades_to_reduce_when_only_one_confirmation_dimension_exists(self) -> None:
        decision = build_decision(
            "TEST",
            6,
            [
                Signal("third_dangerous_upper_wick", 3, True, "third wick"),
                Signal("structure_break", 2, True, "structure break"),
                Signal("sell_warning_state", 1, True, "warning state"),
            ],
            current_price=24.56,
        )
        self.assertEqual(decision.action, Action.REDUCE)
        self.assertIn("清仓二次确认不足", "；".join(decision.reasons))

    def test_falls_back_to_current_price_when_signal_price_missing(self) -> None:
        decision = build_decision(
            "TEST",
            4,
            [Signal("second_dangerous_upper_wick", 4, True, "reduce")],
            current_price=15.67,
        )
        self.assertEqual(decision.current_price, 15.67)

    def test_does_not_replace_report_time_price_with_latest_signal_price(self) -> None:
        decision = build_decision(
            "TEST",
            6,
            [
                Signal("market_weakness", 1, True, "background", triggered_at=datetime(2026, 6, 5, 9, 30), trigger_price=10.01),
                Signal("third_dangerous_upper_wick", 6, True, "core", triggered_at=datetime(2026, 6, 5, 10, 30), trigger_price=10.88),
            ],
            current_price=11.11,
        )
        self.assertEqual(decision.current_price, 11.11)

    def test_background_and_auxiliary_signals_cannot_trigger_reduce_without_core(self) -> None:
        decision = build_decision(
            "TEST",
            6,
            [
                Signal("market_weakness", 2, True, "market weak"),
                Signal("volume_price_anomaly", 2, True, "volume anomaly"),
                Signal("rsi_bearish_divergence", 2, True, "rsi divergence"),
            ],
            current_price=9.99,
        )
        self.assertEqual(Action.HOLD, decision.action)
        self.assertEqual(5, decision.total_score)

    def test_core_signal_with_background_cap_can_trigger_reduce(self) -> None:
        decision = build_decision(
            "TEST",
            99,
            [
                Signal("second_dangerous_upper_wick", 2, True, "second wick"),
                Signal("market_weakness", 3, True, "market weak"),
                Signal("volume_price_anomaly", 1, True, "volume anomaly"),
            ],
            current_price=9.99,
        )
        self.assertEqual(Action.REDUCE, decision.action)
        self.assertEqual(4, decision.total_score)

    def test_exit_requires_core_score_threshold(self) -> None:
        decision = build_decision(
            "TEST",
            99,
            [
                Signal("second_dangerous_upper_wick", 3, True, "core but not enough"),
                Signal("market_weakness", 5, True, "background"),
                Signal("volume_price_anomaly", 3, True, "aux"),
            ],
            current_price=9.99,
        )
        self.assertEqual(Action.REDUCE, decision.action)
        self.assertEqual(7, decision.total_score)

    def test_non_chinese_name_is_not_treated_as_stock_name(self) -> None:
        self.assertIsNone(normalize_symbol_name("TESTA", "Test A"))
        self.assertEqual("TESTA", display_symbol("TESTA", "Test A"))


if __name__ == "__main__":
    unittest.main()
