from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.models import Bar
from sell_monitor.zones.daily_sr_detector import detect_daily_sr_zones


class DailySrDetectorTest(unittest.TestCase):
    def test_detects_repeated_resistance_zone(self) -> None:
        base = datetime(2026, 1, 1)
        bars = []
        highs = [10, 11, 12, 11.8, 12.1, 11.9, 12.0, 11.7, 12.05, 11.8, 11.9, 12.02]
        for idx, high in enumerate(highs):
            bars.append(
                Bar(
                    ts=base + timedelta(days=idx),
                    open=high - 0.6,
                    high=high,
                    low=high - 1.0,
                    close=high - 0.4,
                    volume=1000 + idx * 10,
                )
            )
        zones = detect_daily_sr_zones(bars)
        self.assertTrue(any("resistance" in zone.tags for zone in zones))


if __name__ == "__main__":
    unittest.main()

