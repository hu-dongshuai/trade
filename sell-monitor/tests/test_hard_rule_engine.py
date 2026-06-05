from __future__ import annotations

import unittest

from sell_monitor.domain.enums import Action
from sell_monitor.domain.models import Position, Signal
from sell_monitor.scoring.hard_rule_engine import evaluate_hard_rules


class HardRuleEngineTest(unittest.TestCase):
    def test_third_upper_wick_without_confirmation_downgrades_to_reduce(self) -> None:
        decision = evaluate_hard_rules(
            symbol="002241",
            current_price=25.0,
            position=Position("002241", 20.0, 100),
            rule=None,
            signals=[Signal("third_dangerous_upper_wick", 3, True, "出现第三根危险上影线")],
            symbol_name="歌尔股份",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(Action.REDUCE, decision.action)
        self.assertEqual("歌尔股份", decision.symbol_name)
        self.assertIn("尚未出现破位确认", decision.reasons[0])

    def test_third_upper_wick_with_structure_break_exits(self) -> None:
        decision = evaluate_hard_rules(
            symbol="002241",
            current_price=25.0,
            position=Position("002241", 20.0, 100),
            rule=None,
            signals=[
                Signal("third_dangerous_upper_wick", 3, True, "出现第三根危险上影线"),
                Signal("structure_break", 2, True, "跌破最近一次创出新高后的回调低点"),
            ],
        )

        self.assertIsNotNone(decision)
        self.assertEqual(Action.EXIT_ALL, decision.action)
        self.assertIn("跌破最近一次创出新高后的回调低点", decision.reasons)


if __name__ == "__main__":
    unittest.main()
