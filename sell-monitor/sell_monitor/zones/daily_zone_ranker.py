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


def rank_daily_zones(
    sr_zones: list[PriceZone],
    fvg_zones: list[PriceZone],
    liquidity_zones: list[PriceZone],
    order_blocks: list[PriceZone],
) -> list[PriceZone]:
    ranked = [zone for zone in sr_zones]
    for zone in ranked:
        if any(_overlap_ratio(zone, other) > 0.25 for other in fvg_zones):
            zone.score += 2
            zone.tags.append("with_fvg")
        if any(_overlap_ratio(zone, other) > 0.25 for other in liquidity_zones):
            zone.score += 2
            zone.tags.append("with_liquidity")
        if any(_overlap_ratio(zone, other) > 0.25 for other in order_blocks):
            zone.score += 1
            zone.tags.append("with_order_block")
        if zone.score >= 6:
            zone.level = ZoneLevel.A
        elif zone.score >= 4:
            zone.level = ZoneLevel.B
        elif zone.score >= 2:
            zone.level = ZoneLevel.C
        else:
            zone.level = ZoneLevel.D
    return sorted(ranked, key=lambda zone: (zone.level, -zone.score), reverse=False)

