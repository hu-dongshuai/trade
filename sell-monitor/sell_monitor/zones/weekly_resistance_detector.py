from __future__ import annotations

from datetime import datetime

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.zones.daily_fvg_detector import detect_daily_fvg
from sell_monitor.zones.daily_liquidity_detector import detect_daily_liquidity_zones
from sell_monitor.zones.daily_order_block_detector import detect_daily_order_blocks
from sell_monitor.zones.daily_sr_detector import detect_daily_sr_zones
from sell_monitor.zones.daily_zone_ranker import rank_daily_zones


def detect_weekly_resistance_zones(daily_bars: list[Bar]) -> list[PriceZone]:
    weekly_bars = _to_weekly_bars(daily_bars)
    if len(weekly_bars) < 20:
        return []
    ranked = rank_daily_zones(
        detect_daily_sr_zones(weekly_bars),
        detect_daily_fvg(weekly_bars),
        detect_daily_liquidity_zones(weekly_bars),
        detect_daily_order_blocks(weekly_bars),
    )
    zones: list[PriceZone] = []
    for zone in ranked:
        if "resistance" not in zone.tags:
            continue
        zone.name = zone.name.replace("daily_", "weekly_", 1)
        if not zone.name.startswith("weekly_"):
            zone.name = f"weekly_{zone.name}"
        zone.timeframe = "1w"
        zone.tags = sorted(set(zone.tags + ["weekly_resistance", "higher_timeframe"]))
        zone.importance_score += 1
        zone.score += 1
        zone.level = _promote_one_level(zone.level)
        zones.append(zone)
    return zones


def _to_weekly_bars(daily_bars: list[Bar]) -> list[Bar]:
    if not daily_bars:
        return []
    groups: dict[tuple[int, int], list[Bar]] = {}
    for bar in daily_bars:
        iso = bar.ts.isocalendar()
        groups.setdefault((iso.year, iso.week), []).append(bar)

    weekly: list[Bar] = []
    for _, bars in sorted(groups.items()):
        ordered = sorted(bars, key=lambda item: item.ts)
        first = ordered[0]
        last = ordered[-1]
        weekly.append(
            Bar(
                ts=datetime(last.ts.year, last.ts.month, last.ts.day),
                open=first.open,
                high=max(bar.high for bar in ordered),
                low=min(bar.low for bar in ordered),
                close=last.close,
                volume=sum(bar.volume for bar in ordered),
            )
        )
    return weekly


def _promote_one_level(level: ZoneLevel) -> ZoneLevel:
    if level == ZoneLevel.D:
        return ZoneLevel.C
    if level == ZoneLevel.C:
        return ZoneLevel.B
    if level == ZoneLevel.B:
        return ZoneLevel.A
    return ZoneLevel.A
