from __future__ import annotations

import unittest

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import PriceZone
from sell_monitor.scoring.support_protection import find_ab_level_support_bias


class CongestionSupportProtectionTest(unittest.TestCase):
    def test_support_bias_ignores_primary_congestion_support_when_price_is_far_above(self) -> None:
        support = PriceZone(
            "support_b",
            "1d",
            65.9,
            67.6,
            6,
            ZoneLevel.B,
            ["support", "primary_congestion_support", "congestion_member"],
            4,
        )
        resistance = PriceZone("resistance_a", "1d", 65.8, 75.8, 8, ZoneLevel.A, ["resistance"], 5)

        self.assertIsNone(find_ab_level_support_bias(71.0, [support, resistance]))


if __name__ == "__main__":
    unittest.main()
