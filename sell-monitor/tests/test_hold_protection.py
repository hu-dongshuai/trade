from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.enums import Action, Priority, ZoneLevel
from sell_monitor.domain.models import Bar, DailyContext, Decision, PriceZone
from sell_monitor.scoring.hold_protection import apply_hold_protection_reference, detect_support_liquidity_grab_reclaim


def _bars_with_support_sweep() -> list[Bar]:
    start = datetime(2026, 5, 1, 9, 30)
    bars: list[Bar] = []
    for idx in range(11):
        bars.append(
            Bar(
                ts=start + timedelta(minutes=15 * idx),
                open=100.0,
                high=100.4,
                low=99.6,
                close=100.1,
                volume=1000,
            )
        )
    bars.append(
        Bar(
            ts=start + timedelta(minutes=15 * 11),
            open=98.9,
            high=99.2,
            low=97.8,
            close=98.4,
            volume=1800,
        )
    )
    return bars


class HoldProtectionTest(unittest.TestCase):
    def test_detects_support_liquidity_grab_reclaim(self) -> None:
        support = PriceZone(
            name="daily_support_a",
            timeframe="1d",
            low=98.0,
            high=100.0,
            score=6,
            level=ZoneLevel.A,
            tags=["support"],
            touches=4,
        )

        result = detect_support_liquidity_grab_reclaim(_bars_with_support_sweep(), [support])

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(2, result[0])
        self.assertIn("向下流动性抓取后收回支撑", result[1])

    def test_applies_hold_protection_reference_without_changing_action(self) -> None:
        support = PriceZone(
            name="daily_support_a",
            timeframe="1d",
            low=98.0,
            high=100.0,
            score=6,
            level=ZoneLevel.A,
            tags=["support"],
            touches=4,
        )
        resistance = PriceZone(
            name="daily_resistance_a",
            timeframe="1d",
            low=108.0,
            high=110.0,
            score=6,
            level=ZoneLevel.A,
            tags=["resistance"],
            touches=4,
        )
        decision = Decision(
            symbol="TEST",
            action=Action.REDUCE,
            total_score=5,
            priority=Priority.HIGH,
            reasons=["技术减仓信号"],
            next_step="减仓",
            cancel_condition="信号消失",
        )
        daily_context = DailyContext(
            symbol="TEST",
            current_price=101.0,
            daily_zones=[support, resistance],
            active_zone=resistance,
            daily_trend="up",
            market_state="neutral",
            sector_state="neutral",
        )
        daily_bars = _bars_with_support_sweep()[-10:]
        protected = apply_hold_protection_reference(decision, daily_context, daily_bars, _bars_with_support_sweep())

        self.assertEqual(Action.REDUCE, protected.action)
        self.assertGreaterEqual(protected.hold_protection_score, 3)
        self.assertTrue(protected.hold_protection_reasons)


if __name__ == "__main__":
    unittest.main()
