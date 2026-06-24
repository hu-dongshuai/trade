from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.enums import Action, Priority, ZoneLevel
from sell_monitor.domain.models import Bar, DailyContext, Decision, PriceZone, Signal
from sell_monitor.scoring.support_protection import (
    apply_a_level_support_bias_filter,
    apply_exit_support_protection,
    apply_support_protection,
    find_ab_level_support_bias,
    find_a_level_support_bias,
    find_protective_daily_support,
)


def _bars(count: int, close: float = 102.0) -> list[Bar]:
    start = datetime(2026, 5, 1, 9, 30)
    return [
        Bar(
            ts=start + timedelta(minutes=15 * idx),
            open=close,
            high=close + 0.2,
            low=close - 0.2,
            close=close,
            volume=1000,
        )
        for idx in range(count)
    ]


class SupportProtectionTest(unittest.TestCase):
    def test_downgrades_reduce_above_ab_daily_support(self) -> None:
        support = PriceZone(
            name="daily_support_a",
            timeframe="1d",
            low=98,
            high=100,
            score=6,
            level=ZoneLevel.A,
            tags=["support"],
            touches=4,
        )
        context = DailyContext("TEST", 101.0, [support], None, "up", "neutral", "neutral")
        decision = Decision("TEST", Action.REDUCE, 4, Priority.HIGH, ["普通减仓信号"], "减仓", "信号消失")

        adjusted = apply_support_protection(decision, context, _bars(30, close=101), _bars(25, close=101), [])

        self.assertEqual(Action.HOLD, adjusted.action)
        self.assertIn("强支撑保护过滤", adjusted.reasons[-1])

    def test_keeps_reduce_when_unfilterable_signal_exists(self) -> None:
        support = PriceZone("daily_support_a", "1d", 98, 100, 6, ZoneLevel.A, ["support"], 4)
        context = DailyContext("TEST", 101.0, [support], None, "up", "neutral", "neutral")
        decision = Decision("TEST", Action.REDUCE, 4, Priority.HIGH, ["风险信号"], "减仓", "信号消失")
        signals = [Signal("breakout_failure", 2, True, "突破失败")]

        adjusted = apply_support_protection(decision, context, _bars(30, close=101), _bars(25, close=101), signals)

        self.assertEqual(Action.REDUCE, adjusted.action)

    def test_third_upper_wick_reduce_can_be_downgraded_above_support(self) -> None:
        support = PriceZone("daily_support_a", "1d", 98, 100, 6, ZoneLevel.A, ["support"], 4)
        context = DailyContext("TEST", 101.0, [support], None, "up", "neutral", "neutral")
        decision = Decision("TEST", Action.REDUCE, 5, Priority.HIGH, ["出现第三根危险上影线"], "减仓", "信号消失")
        signals = [Signal("third_dangerous_upper_wick", 3, True, "出现第三根危险上影线")]

        adjusted = apply_support_protection(decision, context, _bars(30, close=101), _bars(25, close=101), signals)

        self.assertEqual(Action.HOLD, adjusted.action)
        self.assertIn("强支撑保护过滤", adjusted.reasons[-1])

    def test_downgrades_third_upper_wick_exit_above_support(self) -> None:
        support = PriceZone("daily_support_a", "1d", 98, 100, 6, ZoneLevel.A, ["support"], 4)
        context = DailyContext("TEST", 101.0, [support], None, "up", "neutral", "neutral")
        decision = Decision(
            "TEST",
            Action.EXIT_ALL,
            5,
            Priority.IMMEDIATE,
            ["出现第三根危险上影线", "放量跌破15分钟MA20"],
            "清仓",
            "信号消失",
        )

        adjusted = apply_exit_support_protection(decision, context, _bars(30, close=101))

        self.assertEqual(Action.REDUCE, adjusted.action)
        self.assertIn("第三根上影线清仓信号降级为减仓", adjusted.reasons[-1])

    def test_ignores_daily_c_d_support_for_protection(self) -> None:
        support = PriceZone("daily_support_c", "1d", 98, 100, 2, ZoneLevel.C, ["support"], 2)

        found = find_protective_daily_support(101.0, [support], _bars(30, close=101))

        self.assertIsNone(found)

    def test_a_level_support_bias_filters_reduce_when_closer_to_support(self) -> None:
        support = PriceZone("support_a", "1d", 98, 100, 7, ZoneLevel.A, ["support"], 5)
        resistance = PriceZone("resistance_a", "1d", 108, 110, 7, ZoneLevel.A, ["resistance"], 5)
        context = DailyContext("TEST", 101.0, [support, resistance], None, "up", "neutral", "neutral")
        decision = Decision("TEST", Action.REDUCE, 5, Priority.HIGH, ["减仓信号"], "减仓", "信号消失")

        adjusted = apply_a_level_support_bias_filter(decision, context)

        self.assertEqual(Action.HOLD, adjusted.action)
        self.assertIn("A级支撑偏置过滤", adjusted.reasons[-1])

    def test_a_level_support_bias_filters_exit_when_closer_to_support(self) -> None:
        support = PriceZone("support_a", "1d", 98, 100, 7, ZoneLevel.A, ["support"], 5)
        resistance = PriceZone("resistance_a", "1d", 108, 110, 7, ZoneLevel.A, ["resistance"], 5)
        context = DailyContext("TEST", 101.0, [support, resistance], None, "up", "neutral", "neutral")
        decision = Decision("TEST", Action.EXIT_ALL, 6, Priority.IMMEDIATE, ["清仓信号"], "清仓", "信号消失")

        adjusted = apply_a_level_support_bias_filter(decision, context)

        self.assertEqual(Action.HOLD, adjusted.action)

    def test_a_level_support_bias_does_not_filter_when_closer_to_resistance(self) -> None:
        support = PriceZone("support_a", "1d", 98, 100, 7, ZoneLevel.A, ["support"], 5)
        resistance = PriceZone("resistance_a", "1d", 103, 105, 7, ZoneLevel.A, ["resistance"], 5)
        context = DailyContext("TEST", 102.5, [support, resistance], None, "up", "neutral", "neutral")
        decision = Decision("TEST", Action.REDUCE, 5, Priority.HIGH, ["减仓信号"], "减仓", "信号消失")

        adjusted = apply_a_level_support_bias_filter(decision, context)

        self.assertEqual(Action.REDUCE, adjusted.action)

    def test_a_level_support_bias_requires_unbroken_support(self) -> None:
        support = PriceZone("support_a", "1d", 98, 100, 7, ZoneLevel.A, ["support"], 5)
        resistance = PriceZone("resistance_a", "1d", 108, 110, 7, ZoneLevel.A, ["resistance"], 5)

        self.assertIsNone(find_a_level_support_bias(97.9, [support, resistance]))

    def test_a_level_support_bias_does_not_filter_manual_hard_exit(self) -> None:
        support = PriceZone("support_a", "1d", 98, 100, 7, ZoneLevel.A, ["support"], 5)
        resistance = PriceZone("resistance_a", "1d", 108, 110, 7, ZoneLevel.A, ["resistance"], 5)
        context = DailyContext("TEST", 101.0, [support, resistance], None, "up", "neutral", "neutral")
        decision = Decision(
            "TEST",
            Action.EXIT_ALL,
            0,
            Priority.IMMEDIATE,
            ["用户设置了硬性清仓规则：计划失效"],
            "清仓",
            "手动取消",
        )

        adjusted = apply_a_level_support_bias_filter(decision, context)

        self.assertEqual(Action.EXIT_ALL, adjusted.action)

    def test_b_level_support_bias_filters_reduce_when_closer_to_support(self) -> None:
        support = PriceZone("support_b", "1d", 98, 100, 5, ZoneLevel.B, ["support"], 4)
        resistance = PriceZone("resistance_b", "1d", 108, 110, 5, ZoneLevel.B, ["resistance"], 4)
        context = DailyContext("TEST", 101.0, [support, resistance], None, "up", "neutral", "neutral")
        decision = Decision("TEST", Action.REDUCE, 5, Priority.HIGH, ["减仓信号"], "减仓", "信号消失")

        adjusted = apply_a_level_support_bias_filter(decision, context)

        self.assertEqual(Action.HOLD, adjusted.action)
        self.assertIn("B级支撑偏置过滤", adjusted.reasons[-1])
        self.assertIsNotNone(find_ab_level_support_bias(101.0, [support, resistance]))

    def test_b_level_support_bias_filters_exit_when_closer_to_support(self) -> None:
        support = PriceZone("support_b", "1d", 98, 100, 5, ZoneLevel.B, ["support"], 4)
        resistance = PriceZone("resistance_b", "1d", 108, 110, 5, ZoneLevel.B, ["resistance"], 4)
        context = DailyContext("TEST", 101.0, [support, resistance], None, "up", "neutral", "neutral")
        decision = Decision("TEST", Action.EXIT_ALL, 6, Priority.IMMEDIATE, ["清仓信号"], "清仓", "信号消失")

        adjusted = apply_a_level_support_bias_filter(decision, context)

        self.assertEqual(Action.HOLD, adjusted.action)

    def test_support_bias_compares_nearest_pressure_across_levels(self) -> None:
        support = PriceZone("support_b", "1d", 98, 100, 5, ZoneLevel.B, ["support"], 4)
        far_b_resistance = PriceZone("resistance_b", "1d", 112, 114, 5, ZoneLevel.B, ["resistance"], 4)
        near_a_resistance = PriceZone("resistance_a", "1d", 103, 105, 8, ZoneLevel.A, ["resistance"], 5)
        context = DailyContext(
            "TEST",
            102.5,
            [support, far_b_resistance, near_a_resistance],
            None,
            "up",
            "neutral",
            "neutral",
        )
        decision = Decision("TEST", Action.REDUCE, 5, Priority.HIGH, ["减仓信号"], "减仓", "信号消失")

        adjusted = apply_a_level_support_bias_filter(decision, context)

        self.assertEqual(Action.REDUCE, adjusted.action)

    def test_support_bias_can_compare_b_support_with_c_pressure(self) -> None:
        support = PriceZone("support_b", "1d", 98, 100, 5, ZoneLevel.B, ["support"], 4)
        resistance = PriceZone("resistance_c", "1d", 108, 110, 3, ZoneLevel.C, ["resistance"], 2)
        context = DailyContext("TEST", 101.0, [support, resistance], None, "up", "neutral", "neutral")
        decision = Decision("TEST", Action.REDUCE, 5, Priority.HIGH, ["减仓信号"], "减仓", "信号消失")

        adjusted = apply_a_level_support_bias_filter(decision, context)

        self.assertEqual(Action.HOLD, adjusted.action)
        self.assertIn("B级支撑偏置过滤", adjusted.reasons[-1])
        self.assertIn("日线C级压力区", adjusted.reasons[-1])
