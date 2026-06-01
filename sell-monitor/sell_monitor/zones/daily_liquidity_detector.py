from __future__ import annotations

from statistics import mean

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.indicators.atr import compute_atr
from sell_monitor.indicators.swing_points import find_swing_highs, find_swing_lows
from sell_monitor.indicators.volume_stats import average_volume


def detect_daily_liquidity_zones(bars: list[Bar]) -> list[PriceZone]:
    if len(bars) < 20:
        return []
    atr = compute_atr(bars, period=14)
    threshold = max(atr * 0.5, bars[-1].close * 0.02)
    zones: list[PriceZone] = []
    avg_all_volume = average_volume(bars[-60:], min(60, len(bars)))

    for label, points, tag in (
        ("high", [(idx, bar.high) for idx, bar in find_swing_highs(bars)], "high_liquidity"),
        ("low", [(idx, bar.low) for idx, bar in find_swing_lows(bars)], "low_liquidity"),
    ):
        clusters: list[list[tuple[int, float]]] = []
        for point in sorted(points, key=lambda item: item[1]):
            value = point[1]
            matched = False
            for cluster in clusters:
                if abs(mean([item[1] for item in cluster]) - value) <= threshold:
                    cluster.append(point)
                    matched = True
                    break
            if not matched:
                clusters.append([point])
        for idx, cluster in enumerate(clusters):
            if len(cluster) < 3:
                continue
            values = [item[1] for item in cluster]
            touch_indices = [item[0] for item in cluster]
            center = mean(values)
            touch_volume = average_volume([bars[item] for item in touch_indices], len(touch_indices))
            large_liquidity = len(cluster) >= 4 or (avg_all_volume > 0 and touch_volume >= avg_all_volume * 1.2)
            tags = [tag, "liquidity_pool"]
            if large_liquidity:
                tags.append("large_liquidity")
            zones.append(
                PriceZone(
                    name=f"daily_liquidity_{label}_{idx}",
                    timeframe="1d",
                    low=center - threshold / 2,
                    high=center + threshold / 2,
                    score=3 if large_liquidity else 2,
                    level=ZoneLevel.C,
                    tags=tags,
                    touches=len(cluster),
                    importance_score=3 if large_liquidity else 2,
                    fragility_score=1 if large_liquidity else 0,
                )
            )

    recent = bars[-20:]
    avg_vol = average_volume(recent, 20)
    band_low = min(bar.low for bar in recent)
    band_high = max(bar.high for bar in recent)
    band_width = band_high - band_low
    avg_range = sum(bar.range for bar in recent) / len(recent)
    if avg_range > 0 and band_width <= avg_range * 1.5 and average_volume(recent, 20) >= avg_vol:
        zones.append(
            PriceZone(
                name="daily_consolidation_liquidity",
                timeframe="1d",
                low=band_low,
                high=band_high,
                score=2,
                level=ZoneLevel.C,
                tags=["consolidation_liquidity", "liquidity_pool"],
                touches=len(recent),
                importance_score=2,
                fragility_score=1,
            )
        )
    return zones
