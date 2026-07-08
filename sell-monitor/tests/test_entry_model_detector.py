from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.entry.model_detector import (
    _has_bullish_reclaim,
    _is_first_pullback_holding,
    _is_near_zone,
    _is_true_breakout,
    _resistance_too_close,
)
from sell_monitor.entry.models import EntryContext


def _bar(
    ts: datetime,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
) -> Bar:
    return Bar(ts=ts, open=open_, high=high, low=low, close=close, volume=volume)


def _context(**overrides) -> EntryContext:
    base = EntryContext(
        symbol="002241",
        symbol_name="歌尔股份",
        current_price=25.0,
        market_state="neutral",
        sector_state="neutral",
        daily_trend="up",
        is_trend_healthy=True,
        is_m60_trend_healthy=True,
        daily_relative_strength_ok=True,
        liquidity_ok=True,
        avg_daily_turnover=350000000.0,
        recent_5d_return=4.2,
        recent_10d_return=8.5,
        weekly_background="A",
        accumulation_score=8,
        accumulation_reasons=["周线接近支撑"],
        weekly_support_zones=[],
        weekly_resistance_zones=[],
        daily_support_zones=[],
        daily_resistance_zones=[],
    )
    values = {**base.__dict__, **overrides}
    return EntryContext(**values)


class EntryModelDetectorTest(unittest.TestCase):
    def test_is_near_zone_accepts_four_percent_gap(self) -> None:
        zone = PriceZone(name="support", timeframe="1d", low=95.8, high=96.0)
        self.assertTrue(_is_near_zone(100.0, zone))

    def test_has_bullish_reclaim_accepts_normal_confirmation(self) -> None:
        start = datetime(2026, 1, 5, 9, 30)
        bars = [
            _bar(start + timedelta(minutes=15 * idx), 10.0, 10.2, 9.9, 10.05, 1000 + idx * 10)
            for idx in range(8)
        ]
        bars.extend(
            [
                _bar(start + timedelta(minutes=15 * 8), 10.05, 10.08, 9.90, 9.95, 1080),
                _bar(start + timedelta(minutes=15 * 9), 9.95, 10.00, 9.85, 9.90, 1100),
                _bar(start + timedelta(minutes=15 * 10), 9.90, 9.94, 9.82, 9.86, 1040),
                _bar(start + timedelta(minutes=15 * 11), 9.88, 10.02, 9.86, 9.98, 1350),
            ]
        )

        self.assertTrue(_has_bullish_reclaim(bars))

    def test_is_true_breakout_accepts_relaxed_body_and_volume(self) -> None:
        start = datetime(2026, 1, 6, 9, 30)
        bars = [
            _bar(start + timedelta(minutes=15 * idx), 10.0, 10.15, 9.98, 10.08, 1000)
            for idx in range(8)
        ]
        bars.extend(
            [
                _bar(start + timedelta(minutes=15 * 8), 10.10, 10.18, 10.05, 10.16, 1100),
                _bar(start + timedelta(minutes=15 * 9), 10.16, 10.62, 10.12, 10.46, 1450),
            ]
        )

        self.assertTrue(_is_true_breakout(bars))

    def test_is_first_pullback_holding_accepts_two_bar_combo(self) -> None:
        start = datetime(2026, 1, 7, 13, 0)
        bars = [
            _bar(start + timedelta(minutes=15 * idx), 10.0, 10.10, 9.96, 10.05, 1000)
            for idx in range(9)
        ]
        bars.extend(
            [
                _bar(start + timedelta(minutes=15 * 9), 10.05, 10.45, 10.03, 10.36, 1500),
                _bar(start + timedelta(minutes=15 * 10), 10.34, 10.38, 10.22, 10.31, 1200),
                _bar(start + timedelta(minutes=15 * 11), 10.30, 10.40, 10.28, 10.34, 1100),
            ]
        )

        self.assertTrue(_is_first_pullback_holding(bars))

    def test_resistance_too_close_uses_relaxed_ratio(self) -> None:
        context = _context(current_price=10.0)
        support = PriceZone(name="support", timeframe="1d", low=9.0, high=9.4)
        target = PriceZone(name="resistance", timeframe="1d", low=11.9, high=12.2)

        self.assertFalse(_resistance_too_close(context, support, target))


if __name__ == "__main__":
    unittest.main()
