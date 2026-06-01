from __future__ import annotations

import unittest

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import PriceZone
from sell_monitor.zones.daily_zone_ranker import rank_daily_zones


class DailyZoneRankerTest(unittest.TestCase):
    def test_a_level_requires_fvg_and_liquidity_confluence(self) -> None:
        sr = PriceZone(
            "daily_resistance",
            "1d",
            100,
            102,
            score=2,
            level=ZoneLevel.C,
            tags=["resistance"],
            touches=3,
            importance_score=3,
        )
        fvg = PriceZone(
            "bearish_fvg",
            "1d",
            100.5,
            101.5,
            score=2,
            level=ZoneLevel.C,
            tags=["daily_fvg", "bearish_fvg", "fresh_fvg"],
            importance_score=3,
            invalidation_price=101.5,
        )
        liquidity = PriceZone(
            "equal_highs",
            "1d",
            100.8,
            101.8,
            score=3,
            level=ZoneLevel.C,
            tags=["high_liquidity", "liquidity_pool", "large_liquidity"],
            touches=4,
            importance_score=3,
        )

        ranked = rank_daily_zones([sr], [fvg], [liquidity], [])

        self.assertEqual(ZoneLevel.A, ranked[0].level)
        self.assertIn("with_fvg", ranked[0].tags)
        self.assertIn("with_large_liquidity", ranked[0].tags)
        self.assertGreaterEqual(ranked[0].importance_score, 9)

    def test_sr_without_confluence_is_not_promoted_to_ab(self) -> None:
        sr = PriceZone(
            "many_touch_resistance",
            "1d",
            100,
            102,
            score=4,
            level=ZoneLevel.C,
            tags=["resistance", "many_touches"],
            touches=6,
            importance_score=4,
            fragility_score=2,
        )

        ranked = rank_daily_zones([sr], [], [], [])

        self.assertNotIn(ranked[0].level, {ZoneLevel.A, ZoneLevel.B})

    def test_weekly_resistance_promotes_overlapping_daily_resistance_one_level(self) -> None:
        sr = PriceZone(
            "daily_resistance",
            "1d",
            100,
            102,
            score=3,
            level=ZoneLevel.C,
            tags=["resistance"],
            touches=2,
            importance_score=3,
        )
        weekly = PriceZone(
            "weekly_resistance",
            "1w",
            100.5,
            101.5,
            score=3,
            level=ZoneLevel.C,
            tags=["resistance", "weekly_resistance"],
            touches=2,
            importance_score=3,
        )

        ranked = rank_daily_zones([sr], [], [], [], weekly_resistance_zones=[weekly])
        daily = next(zone for zone in ranked if zone.name == "daily_resistance")

        self.assertEqual(ZoneLevel.B, daily.level)
        self.assertIn("with_weekly_resistance", daily.tags)

    def test_fibonacci_resistance_adds_low_weight_confluence(self) -> None:
        sr = PriceZone(
            "daily_resistance",
            "1d",
            100,
            102,
            score=2,
            level=ZoneLevel.C,
            tags=["resistance"],
            touches=2,
            importance_score=2,
        )
        fib = PriceZone(
            "daily_fib",
            "1d",
            100.5,
            101.5,
            score=3,
            level=ZoneLevel.C,
            tags=["resistance", "daily_fibonacci"],
            importance_score=3,
        )

        ranked = rank_daily_zones([sr], [], [], [], fibonacci_zones=[fib])
        daily = next(zone for zone in ranked if zone.name == "daily_resistance")

        self.assertIn("with_fibonacci", daily.tags)
        self.assertGreaterEqual(daily.importance_score, 3)


if __name__ == "__main__":
    unittest.main()
