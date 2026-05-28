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


if __name__ == "__main__":
    unittest.main()

