from __future__ import annotations

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import PriceZone


def _overlap_ratio(a: PriceZone, b: PriceZone) -> float:
    low = max(a.low, b.low)
    high = min(a.high, b.high)
    if high <= low:
        return 0.0
    overlap = high - low
    width = max(a.high - a.low, b.high - b.low, 1e-9)
    return overlap / width


def _best_overlap(zone: PriceZone, zones: list[PriceZone]) -> PriceZone | None:
    matches = [other for other in zones if _overlap_ratio(zone, other) > 0.20]
    if not matches:
        return None
    return max(matches, key=lambda other: _overlap_ratio(zone, other))


def rank_daily_zones(
    sr_zones: list[PriceZone],
    fvg_zones: list[PriceZone],
    liquidity_zones: list[PriceZone],
    order_blocks: list[PriceZone],
    weekly_resistance_zones: list[PriceZone] | None = None,
    fibonacci_zones: list[PriceZone] | None = None,
) -> list[PriceZone]:
    weekly_resistance_zones = weekly_resistance_zones or []
    fibonacci_zones = fibonacci_zones or []
    ranked = [zone for zone in sr_zones]
    for zone in ranked:
        importance = max(zone.importance_score, zone.score)
        fragility = zone.fragility_score
        fvg = _best_overlap(zone, fvg_zones)
        liquidity = _best_overlap(zone, liquidity_zones)
        order_block = _best_overlap(zone, order_blocks)
        weekly = _best_overlap(zone, weekly_resistance_zones) if "resistance" in zone.tags else None
        fibonacci = _best_overlap(zone, fibonacci_zones) if "resistance" in zone.tags else None

        if fvg is not None:
            importance += 3
            zone.tags.append("with_fvg")
            if "fresh_fvg" in fvg.tags:
                importance += 1
                zone.tags.append("with_fresh_fvg")
            elif "partially_filled_fvg" in fvg.tags:
                zone.tags.append("with_partially_filled_fvg")
            if zone.invalidation_price is None:
                zone.invalidation_price = fvg.invalidation_price
        if liquidity is not None:
            importance += 2
            zone.tags.append("with_liquidity")
            fragility += 1
            if "large_liquidity" in liquidity.tags:
                importance += 1
                zone.tags.append("with_large_liquidity")
        if order_block is not None:
            importance += 1
            zone.tags.append("with_order_block")
        if fibonacci is not None:
            importance += 1
            zone.tags.append("with_fibonacci")
        if weekly is not None:
            importance += 2
            zone.tags.append("with_weekly_resistance")

        net_score = max(0, importance - min(fragility, 2))
        zone.importance_score = importance
        zone.fragility_score = fragility
        zone.score = net_score

        has_fvg = "with_fvg" in zone.tags
        has_liquidity = "with_liquidity" in zone.tags
        if net_score >= 7 and has_fvg and (has_liquidity or zone.touches >= 3):
            zone.level = ZoneLevel.A
        elif net_score >= 5 and (has_fvg or has_liquidity):
            zone.level = ZoneLevel.B
        elif net_score >= 3:
            zone.level = ZoneLevel.C
        else:
            zone.level = ZoneLevel.D
        if weekly is not None:
            zone.level = _promote_one_level(zone.level)
    ranked.extend(fibonacci_zones)
    ranked.extend(weekly_resistance_zones)
    return sorted(ranked, key=lambda zone: (zone.level, -zone.score, zone.fragility_score), reverse=False)


def _promote_one_level(level: ZoneLevel) -> ZoneLevel:
    if level == ZoneLevel.D:
        return ZoneLevel.C
    if level == ZoneLevel.C:
        return ZoneLevel.B
    if level == ZoneLevel.B:
        return ZoneLevel.A
    return ZoneLevel.A
