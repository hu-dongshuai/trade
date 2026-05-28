from __future__ import annotations

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.indicators.atr import compute_atr
from sell_monitor.indicators.swing_points import find_swing_highs


def detect_intraday_resistance_near_active_zone(bars: list[Bar], active_zone: PriceZone) -> list[PriceZone]:
    if len(bars) < 10:
        return []
    atr = compute_atr(bars, period=14)
    threshold = max(atr * 0.5, bars[-1].close * 0.008)
    zones: list[PriceZone] = []
    for idx, bar in find_swing_highs(bars):
        if active_zone.low - threshold <= bar.high <= active_zone.high + threshold:
            zones.append(
                PriceZone(
                    name=f"m15_resistance_{idx}",
                    timeframe="15m",
                    low=bar.high - threshold / 2,
                    high=bar.high + threshold / 2,
                    score=1,
                    level=ZoneLevel.C,
                    tags=["m15_resistance"],
                )
            )
    return zones

