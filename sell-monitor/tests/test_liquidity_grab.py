from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.signals.liquidity_grab import detect_resistance_liquidity_grab


class LiquidityGrabTest(unittest.TestCase):
    def test_detects_high_volume_sweep_above_resistance_then_close_back_below(self) -> None:
        start = datetime(2026, 5, 29, 9, 30)
        bars = [
            Bar(start + timedelta(minutes=15 * idx), 100, 101, 99, 100, 1000)
            for idx in range(11)
        ]
        bars.append(Bar(start + timedelta(minutes=15 * 11), 101, 106, 100.5, 103.8, 1600))
        zone = PriceZone("resistance", "1d", 103, 104, 5, ZoneLevel.B, ["resistance"], 3)

        signal = detect_resistance_liquidity_grab(bars, zone)

        self.assertIsNotNone(signal)
        self.assertEqual(3, signal.score)
        self.assertEqual("resistance_liquidity_grab", signal.name)

    def test_ignores_breakout_that_holds_above_resistance(self) -> None:
        start = datetime(2026, 5, 29, 9, 30)
        bars = [
            Bar(start + timedelta(minutes=15 * idx), 100, 101, 99, 100, 1000)
            for idx in range(11)
        ]
        bars.append(Bar(start + timedelta(minutes=15 * 11), 104, 106, 103.5, 105, 1600))
        zone = PriceZone("resistance", "1d", 103, 104, 5, ZoneLevel.B, ["resistance"], 3)

        signal = detect_resistance_liquidity_grab(bars, zone)

        self.assertIsNone(signal)


if __name__ == "__main__":
    unittest.main()
