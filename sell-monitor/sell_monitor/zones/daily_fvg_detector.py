from __future__ import annotations

from statistics import mean

from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.indicators.volume_stats import average_volume


def detect_daily_fvg(bars: list[Bar]) -> list[PriceZone]:
    zones: list[PriceZone] = []
    if len(bars) < 3:
        return zones
    for idx in range(len(bars) - 2):
        first, second, third = bars[idx], bars[idx + 1], bars[idx + 2]
        prior_bars = bars[max(0, idx - 9): idx + 1]
        prior_avg_body = mean([bar.body for bar in prior_bars]) if prior_bars else 0.0
        prior_avg_volume = average_volume(prior_bars, 10)
        bullish_gap = third.low > first.high
        bearish_gap = third.high < first.low
        strong_body = prior_avg_body > 0 and second.body >= prior_avg_body * 1.5
        strong_volume = second.volume >= prior_avg_volume * 1.5 if prior_avg_volume else False
        if bullish_gap and (strong_body or strong_volume):
            low, high = first.high, third.low
            fill_state = _bullish_fill_state(bars[idx + 3 :], low, high)
            if fill_state == "filled":
                continue
            zones.append(
                PriceZone(
                    name=f"daily_bullish_fvg_{idx}",
                    timeframe="1d",
                    low=low,
                    high=high,
                    score=2,
                    level=ZoneLevel.C,
                    tags=["daily_fvg", "bullish_fvg", "support", fill_state],
                    importance_score=3 if fill_state == "fresh_fvg" else 2,
                    invalidation_price=low,
                )
            )
        if bearish_gap and (strong_body or strong_volume):
            low, high = third.high, first.low
            fill_state = _bearish_fill_state(bars[idx + 3 :], low, high)
            if fill_state == "filled":
                continue
            zones.append(
                PriceZone(
                    name=f"daily_bearish_fvg_{idx}",
                    timeframe="1d",
                    low=low,
                    high=high,
                    score=2,
                    level=ZoneLevel.C,
                    tags=["daily_fvg", "bearish_fvg", "resistance", fill_state],
                    importance_score=3 if fill_state == "fresh_fvg" else 2,
                    invalidation_price=high,
                )
            )
    return zones


def _bullish_fill_state(future_bars: list[Bar], low: float, high: float) -> str:
    touched = False
    for bar in future_bars:
        if bar.low <= low:
            return "filled"
        if bar.low <= high:
            touched = True
    return "partially_filled_fvg" if touched else "fresh_fvg"


def _bearish_fill_state(future_bars: list[Bar], low: float, high: float) -> str:
    touched = False
    for bar in future_bars:
        if bar.high >= high:
            return "filled"
        if bar.high >= low:
            touched = True
    return "partially_filled_fvg" if touched else "fresh_fvg"
