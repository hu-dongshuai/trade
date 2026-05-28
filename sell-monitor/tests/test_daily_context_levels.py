from __future__ import annotations

import unittest

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import PriceZone
from sell_monitor.monitor.daily_context_builder import _daily_ab_zones


class DailyContextLevelsTest(unittest.TestCase):
    def test_daily_context_keeps_only_a_b_zones(self) -> None:
        zones = [
            PriceZone("a", "1d", 10, 11, 6, ZoneLevel.A, ["resistance"], 3),
            PriceZone("b", "1d", 9, 10, 4, ZoneLevel.B, ["support"], 3),
            PriceZone("c", "1d", 8, 9, 2, ZoneLevel.C, ["support"], 2),
            PriceZone("d", "1d", 7, 8, 1, ZoneLevel.D, ["resistance"], 1),
        ]

        filtered = _daily_ab_zones(zones)

        self.assertEqual(["a", "b"], [zone.name for zone in filtered])
