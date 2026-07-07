from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.zones.daily_zone_filter import filter_current_daily_zones, prepare_daily_zones


def _daily_bars(closes: list[float]) -> list[Bar]:
    start = datetime(2026, 1, 1)
    return [
        Bar(start + timedelta(days=idx), close - 0.2, close + 0.5, close - 0.5, close, 1000)
        for idx, close in enumerate(closes)
    ]


class DailyZoneFilterTest(unittest.TestCase):
    def test_discards_resistance_after_effective_breakout(self) -> None:
        zone = PriceZone(
            "old_resistance",
            "1d",
            100,
            102,
            score=6,
            level=ZoneLevel.A,
            tags=["resistance"],
            invalidation_price=102.5,
        )

        filtered = prepare_daily_zones([zone], _daily_bars([99, 101, 103, 104]), daily_atr=2.0)

        self.assertEqual([], filtered)

    def test_keeps_resistance_when_breakout_happened_before_latest_touch(self) -> None:
        zone = PriceZone(
            "retested_resistance",
            "1d",
            100,
            102,
            score=6,
            level=ZoneLevel.A,
            tags=["resistance"],
            invalidation_price=102.5,
        )

        filtered = prepare_daily_zones([zone], _daily_bars([103, 104, 101, 99]), daily_atr=2.0)

        self.assertEqual(1, len(filtered))
        self.assertEqual("retested_resistance", filtered[0].name)

    def test_merges_nearby_resistances(self) -> None:
        left = PriceZone("r1", "1d", 100, 102, 5, ZoneLevel.B, ["resistance"], 2, 5)
        right = PriceZone("r2", "1d", 102.6, 104, 7, ZoneLevel.A, ["resistance", "with_fvg"], 3, 7)

        filtered = prepare_daily_zones([left, right], _daily_bars([95, 96, 97, 98]), daily_atr=2.0)

        self.assertEqual(1, len(filtered))
        self.assertEqual(ZoneLevel.A, filtered[0].level)
        self.assertEqual(100, filtered[0].low)
        self.assertEqual(104, filtered[0].high)
        self.assertIn("merged_resistance", filtered[0].tags)

    def test_far_resistance_is_downgraded_or_display_only(self) -> None:
        far = PriceZone("far", "1d", 130, 132, 7, ZoneLevel.A, ["resistance", "with_fvg"], 2, 7)
        very_far = PriceZone("very_far", "1d", 150, 152, 7, ZoneLevel.A, ["resistance", "with_fvg"], 2, 7)

        filtered = filter_current_daily_zones([far, very_far], current_price=100)

        self.assertEqual(ZoneLevel.B, filtered[0].level)
        self.assertIn("far_resistance_downgraded", filtered[0].tags)
        self.assertEqual(ZoneLevel.D, filtered[1].level)
        self.assertIn("display_only_far_resistance", filtered[1].tags)

    def test_standalone_fibonacci_is_display_only(self) -> None:
        fib = PriceZone("fib", "1d", 105, 106, 3, ZoneLevel.C, ["resistance", "daily_fibonacci"], 0, 3)

        filtered = filter_current_daily_zones([fib], current_price=100)

        self.assertEqual(ZoneLevel.D, filtered[0].level)
        self.assertIn("display_only_fibonacci", filtered[0].tags)

    def test_weak_c_resistance_is_downgraded_unless_near_or_confluent(self) -> None:
        weak = PriceZone("weak_c", "1d", 115, 116, 3, ZoneLevel.C, ["resistance"], 1, 3)
        near = PriceZone("near_c", "1d", 106, 107, 3, ZoneLevel.C, ["resistance"], 1, 3)
        confluent = PriceZone("with_fvg", "1d", 115, 116, 3, ZoneLevel.C, ["resistance", "with_fvg"], 1, 3)

        filtered = filter_current_daily_zones([weak, near, confluent], current_price=100)

        self.assertEqual(ZoneLevel.D, filtered[0].level)
        self.assertEqual(ZoneLevel.C, filtered[1].level)
        self.assertEqual(ZoneLevel.C, filtered[2].level)

    def test_marks_dense_mixed_band_as_congestion_and_hides_inner_zones(self) -> None:
        resistance = PriceZone("resistance_a", "1d", 65.8, 75.8, 8, ZoneLevel.A, ["resistance"], 8, 9, 5)
        support_lower = PriceZone("support_b1", "1d", 65.9, 67.6, 6, ZoneLevel.B, ["support"], 6, 8, 4)
        support_middle = PriceZone("support_b2", "1d", 68.4, 70.1, 7, ZoneLevel.B, ["support"], 4, 8, 1)
        support_upper = PriceZone("support_b3", "1d", 74.7, 76.3, 6, ZoneLevel.B, ["support"], 4, 7, 1)

        filtered = prepare_daily_zones(
            [resistance, support_lower, support_middle, support_upper],
            _daily_bars([64, 66, 68, 70, 72, 74]),
            daily_atr=2.0,
        )

        congestion = next(zone for zone in filtered if "congestion_zone" in zone.tags)
        self.assertAlmostEqual(65.8, congestion.low)
        self.assertAlmostEqual(76.3, congestion.high)
        lower = next(zone for zone in filtered if zone.name == "support_b1")
        middle = next(zone for zone in filtered if zone.name == "support_b2")
        upper = next(zone for zone in filtered if zone.name == "support_b3")
        self.assertIn("primary_congestion_support", lower.tags)
        self.assertIn("inner_congestion_zone", middle.tags)
        self.assertIn("display_hidden", middle.tags)
        self.assertNotIn("display_hidden", upper.tags)


if __name__ == "__main__":
    unittest.main()
