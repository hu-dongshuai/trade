from __future__ import annotations

from statistics import mean

from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.indicators.atr import compute_atr
from sell_monitor.indicators.swing_points import find_swing_highs, find_swing_lows


def _cluster_levels(values: list[float], threshold: float) -> list[list[float]]:
    clusters: list[list[float]] = []
    for value in sorted(values):
        placed = False
        for cluster in clusters:
            if abs(mean(cluster) - value) <= threshold:
                cluster.append(value)
                placed = True
                break
        if not placed:
            clusters.append([value])
    return clusters


def detect_daily_sr_zones(bars: list[Bar]) -> list[PriceZone]:
    if len(bars) < 10:
        return []
    atr = compute_atr(bars, period=14)
    threshold = max(atr * 0.5, bars[-1].close * 0.02)

    high_points = [bar.high for _, bar in find_swing_highs(bars)]
    low_points = [bar.low for _, bar in find_swing_lows(bars)]

    zones: list[PriceZone] = []
    for idx, cluster in enumerate(_cluster_levels(high_points, threshold)):
        if len(cluster) < 2:
            continue
        center = mean(cluster)
        zones.append(
            PriceZone(
                name=f"daily_resistance_{idx}",
                timeframe="1d",
                low=center - threshold / 2,
                high=center + threshold / 2,
                score=2,
                level=ZoneLevel.C,
                tags=["resistance"],
                touches=len(cluster),
            )
        )
    for idx, cluster in enumerate(_cluster_levels(low_points, threshold)):
        if len(cluster) < 2:
            continue
        center = mean(cluster)
        zones.append(
            PriceZone(
                name=f"daily_support_{idx}",
                timeframe="1d",
                low=center - threshold / 2,
                high=center + threshold / 2,
                score=2,
                level=ZoneLevel.C,
                tags=["support"],
                touches=len(cluster),
            )
        )
    return zones

