from __future__ import annotations

from statistics import mean

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.indicators.atr import compute_atr
from sell_monitor.indicators.swing_points import find_swing_highs, find_swing_lows


def _cluster_levels(points: list[tuple[int, float]], threshold: float) -> list[list[tuple[int, float]]]:
    clusters: list[list[tuple[int, float]]] = []
    for point in sorted(points, key=lambda item: item[1]):
        value = point[1]
        placed = False
        for cluster in clusters:
            if abs(mean([item[1] for item in cluster]) - value) <= threshold:
                cluster.append(point)
                placed = True
                break
        if not placed:
            clusters.append([point])
    return clusters


def detect_daily_sr_zones(bars: list[Bar]) -> list[PriceZone]:
    if len(bars) < 10:
        return []
    atr = compute_atr(bars, period=14)
    latest_close = bars[-1].close
    cluster_threshold = max(atr * 0.45, latest_close * 0.012)
    zone_half_width = min(max(atr * 0.25, latest_close * 0.006), latest_close * 0.018)
    invalidation_pad = min(max(atr * 0.25, latest_close * 0.005), latest_close * 0.015)

    high_points = [(idx, bar.high) for idx, bar in find_swing_highs(bars)]
    low_points = [(idx, bar.low) for idx, bar in find_swing_lows(bars)]

    zones: list[PriceZone] = []
    for idx, cluster in enumerate(_cluster_levels(high_points, cluster_threshold)):
        if len(cluster) < 2:
            continue
        values = [item[1] for item in cluster]
        center = mean(values)
        touches = len(cluster)
        bars_since_touch = len(bars) - 1 - max(item[0] for item in cluster)
        importance = 2 + min(max(touches - 2, 0), 2)
        fragility = _fragility_from_touches(touches, bars_since_touch)
        tags = ["resistance"] + _freshness_tags(touches, bars_since_touch)
        zones.append(
            PriceZone(
                name=f"daily_resistance_{idx}",
                timeframe="1d",
                low=center - zone_half_width,
                high=center + zone_half_width,
                score=2,
                level=ZoneLevel.C,
                tags=tags,
                touches=touches,
                importance_score=importance,
                fragility_score=fragility,
                invalidation_price=center + zone_half_width + invalidation_pad,
            )
        )
    for idx, cluster in enumerate(_cluster_levels(low_points, cluster_threshold)):
        if len(cluster) < 2:
            continue
        values = [item[1] for item in cluster]
        center = mean(values)
        touches = len(cluster)
        bars_since_touch = len(bars) - 1 - max(item[0] for item in cluster)
        importance = 2 + min(max(touches - 2, 0), 2)
        fragility = _fragility_from_touches(touches, bars_since_touch)
        tags = ["support"] + _freshness_tags(touches, bars_since_touch)
        zones.append(
            PriceZone(
                name=f"daily_support_{idx}",
                timeframe="1d",
                low=center - zone_half_width,
                high=center + zone_half_width,
                score=2,
                level=ZoneLevel.C,
                tags=tags,
                touches=touches,
                importance_score=importance,
                fragility_score=fragility,
                invalidation_price=center - zone_half_width - invalidation_pad,
            )
        )
    return zones


def _freshness_tags(touches: int, bars_since_touch: int) -> list[str]:
    tags: list[str] = []
    if bars_since_touch >= 15:
        tags.append("fresh_zone")
    elif bars_since_touch <= 5:
        tags.append("recently_tested")
    if touches >= 5:
        tags.append("many_touches")
    return tags


def _fragility_from_touches(touches: int, bars_since_touch: int) -> int:
    fragility = max(touches - 4, 0)
    if bars_since_touch <= 5:
        fragility += 1
    return fragility
