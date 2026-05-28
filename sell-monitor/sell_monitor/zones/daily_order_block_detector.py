from __future__ import annotations

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone


def detect_daily_order_blocks(bars: list[Bar]) -> list[PriceZone]:
    zones: list[PriceZone] = []
    if len(bars) < 4:
        return zones
    for idx in range(1, len(bars) - 1):
        prev_bar, bar, next_bar = bars[idx - 1], bars[idx], bars[idx + 1]
        if bar.is_bearish and next_bar.close > bar.high and next_bar.body > prev_bar.body:
            zones.append(
                PriceZone(
                    name=f"daily_order_block_{idx}",
                    timeframe="1d",
                    low=bar.low,
                    high=bar.high,
                    score=1,
                    level=ZoneLevel.D,
                    tags=["order_block"],
                )
            )
    return zones

