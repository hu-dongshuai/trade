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

    for label, points, tag in (
        ("high", [bar.high for _, bar in find_swing_highs(bars)], "high_liquidity"),
        ("low", [bar.low for _, bar in find_swing_lows(bars)], "low_liquidity"),
    ):
        clusters: list[list[float]] = []
        for value in sorted(points):
            matched = False
            for cluster in clusters:
                if abs(mean(cluster) - value) <= threshold:
                    cluster.append(value)
                    matched = True
                    break
            if not matched:
                clusters.append([value])
        for idx, cluster in enumerate(clusters):
            if len(cluster) < 3:
                continue
            center = mean(cluster)
            zones.append(
                PriceZone(
                    name=f"daily_liquidity_{label}_{idx}",
                    timeframe="1d",
                    low=center - threshold / 2,
                    high=center + threshold / 2,
                    score=2,
                    level=ZoneLevel.C,
                    tags=[tag],
                    touches=len(cluster),
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
                tags=["consolidation_liquidity"],
                touches=len(recent),
            )
        )
    return zones

