from __future__ import annotations

import unittest

from sell_monitor.app.backtest import BacktestResult, format_backtest_report
from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import PriceZone


class BacktestReportZonesTest(unittest.TestCase):
    def test_report_includes_zone_table_near_top(self) -> None:
        zone = PriceZone(
            name="daily_support",
            timeframe="1d",
            low=20.0,
            high=21.0,
            score=6,
            level=ZoneLevel.B,
            tags=["support", "with_fvg"],
            touches=3,
            importance_score=7,
            fragility_score=1,
            invalidation_price=19.8,
        )
        result = BacktestResult(events=[], notices=[], zone_snapshots={"002241": [zone]})

        report = format_backtest_report(result, "2026-01-01", "2026-01-31")

        self.assertIn("| 002241 | 1d | B |", report)
        self.assertIn("20.00 | 21.00 | 6 | 7 | 1 | 19.80 | 3 | support, with_fvg |", report)


if __name__ == "__main__":
    unittest.main()
