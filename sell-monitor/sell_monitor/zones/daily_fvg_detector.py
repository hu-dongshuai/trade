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
            zones.append(
                PriceZone(
                    name=f"daily_bullish_fvg_{idx}",
                    timeframe="1d",
                    low=first.high,
                    high=third.low,
                    score=2,
                    level=ZoneLevel.C,
                    tags=["daily_fvg", "bullish_fvg"],
                )
            )
        if bearish_gap and (strong_body or strong_volume):
            zones.append(
                PriceZone(
                    name=f"daily_bearish_fvg_{idx}",
                    timeframe="1d",
                    low=third.high,
                    high=first.low,
                    score=2,
                    level=ZoneLevel.C,
                    tags=["daily_fvg", "bearish_fvg"],
                )
            )
    return zones
