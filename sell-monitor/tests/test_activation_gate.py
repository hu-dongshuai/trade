from __future__ import annotations

import unittest

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import PriceZone
from sell_monitor.zones.activation_gate import find_active_zone


class ActivationGateTest(unittest.TestCase):
    def test_returns_active_zone_when_price_is_close(self) -> None:
        zone = PriceZone(
            name="daily_resistance",
            timeframe="1d",
            low=100.0,
            high=102.0,
            score=6,
            level=ZoneLevel.A,
            tags=["resistance"],
        )
        active = find_active_zone(102.3, 1.0, [zone])
        self.assertIsNotNone(active)

    def test_c_level_resistance_can_activate_monitoring(self) -> None:
        zone = PriceZone(
            name="daily_resistance_c",
            timeframe="1d",
            low=100.0,
            high=102.0,
            score=3,
            level=ZoneLevel.C,
            tags=["resistance", "daily_fibonacci"],
        )

        active = find_active_zone(101.5, 1.0, [zone])

        self.assertIsNotNone(active)

    def test_c_level_support_does_not_activate_monitoring(self) -> None:
        zone = PriceZone(
            name="daily_support_c",
            timeframe="1d",
            low=100.0,
            high=102.0,
            score=3,
            level=ZoneLevel.C,
            tags=["support"],
        )

        active = find_active_zone(101.5, 1.0, [zone])

        self.assertIsNone(active)

    def test_congestion_mid_does_not_activate_monitoring(self) -> None:
        resistance = PriceZone(
            name="daily_resistance_a",
            timeframe="1d",
            low=65.8,
            high=75.8,
            score=8,
            level=ZoneLevel.A,
            tags=["resistance", "primary_congestion_resistance", "congestion_member"],
        )
        congestion = PriceZone(
            name="daily_congestion_0",
            timeframe="mixed",
            low=65.8,
            high=75.8,
            score=8,
            level=ZoneLevel.A,
            tags=["congestion_zone", "support", "resistance"],
        )

        active = find_active_zone(70.5, 1.0, [resistance, congestion])

        self.assertIsNone(active)

    def test_prefers_narrower_support_when_support_and_resistance_overlap(self) -> None:
        support = PriceZone(
            name="support_b",
            timeframe="1d",
            low=64.4,
            high=66.1,
            score=7,
            level=ZoneLevel.A,
            tags=["support", "primary_congestion_support"],
        )
        resistance = PriceZone(
            name="resistance_a",
            timeframe="1d",
            low=64.8,
            high=77.0,
            score=8,
            level=ZoneLevel.A,
            tags=["resistance", "primary_congestion_resistance"],
        )

        active = find_active_zone(65.8, 1.0, [support, resistance])

        self.assertIsNotNone(active)
        self.assertEqual("support_b", active.name)


if __name__ == "__main__":
    unittest.main()
