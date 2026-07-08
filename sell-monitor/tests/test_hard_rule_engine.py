from __future__ import annotations

import unittest
from datetime import datetime

from sell_monitor.domain.enums import Action
from sell_monitor.domain.models import Position, Signal, UserRule
from sell_monitor.scoring.hard_rule_engine import evaluate_hard_rules


class HardRuleEngineTest(unittest.TestCase):
    def test_third_upper_wick_without_confirmation_uses_actual_signal_score(self) -> None:
        decision = evaluate_hard_rules(
            symbol="002241",
            current_price=25.0,
            position=Position("002241", 20.0, 100),
            rule=None,
            signals=[
                Signal(
                    "third_dangerous_upper_wick",
                    3,
                    True,
                    "出现第三根危险上影线（10:15）",
                    triggered_at=datetime(2026, 6, 5, 10, 15),
                    trigger_price=24.94,
                )
            ],
            symbol_name="歌尔股份",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(Action.REDUCE, decision.action)
        self.assertEqual("歌尔股份", decision.symbol_name)
        self.assertEqual(25.0, decision.current_price)
        self.assertEqual(3, decision.total_score)
        self.assertIn("尚未出现破位确认", decision.reasons[0])

    def test_third_upper_wick_with_single_confirmation_still_only_reduces(self) -> None:
        decision = evaluate_hard_rules(
            symbol="002241",
            current_price=25.0,
            position=Position("002241", 20.0, 100),
            rule=None,
            signals=[
                Signal("third_dangerous_upper_wick", 3, True, "出现第三根危险上影线（10:00）"),
                Signal("structure_break", 2, True, "跌破最近一次创出新高后的回调低点"),
            ],
        )

        self.assertIsNotNone(decision)
        self.assertEqual(Action.REDUCE, decision.action)
        self.assertIn("清仓二次确认仍不足", "；".join(decision.reasons))

    def test_third_upper_wick_with_two_confirmation_dimensions_exits(self) -> None:
        decision = evaluate_hard_rules(
            symbol="002241",
            current_price=25.0,
            position=Position("002241", 20.0, 100),
            rule=None,
            signals=[
                Signal("third_dangerous_upper_wick", 3, True, "出现第三根危险上影线（10:00）"),
                Signal("structure_break", 2, True, "跌破最近一次创出新高后的回调低点"),
                Signal("m15_ma20_high_volume_break", 2, True, "14:00 这根15分钟K线放量，且连续两根15分钟K线收在 MA20 下方"),
            ],
        )

        self.assertIsNotNone(decision)
        self.assertEqual(Action.EXIT_ALL, decision.action)
        self.assertEqual(7, decision.total_score)

    def test_manual_stop_loss_does_not_invent_score(self) -> None:
        decision = evaluate_hard_rules(
            symbol="002241",
            current_price=25.0,
            position=Position("002241", 20.0, 100),
            rule=UserRule(symbol="002241", stop_loss=25.5),
            signals=[],
        )

        self.assertIsNotNone(decision)
        self.assertEqual(Action.STOP_LOSS, decision.action)
        self.assertEqual(0, decision.total_score)


if __name__ == "__main__":
    unittest.main()
