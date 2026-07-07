from __future__ import annotations

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone


def prepare_daily_zones(zones: list[PriceZone], daily_bars: list[Bar], daily_atr: float) -> list[PriceZone]:
    unbroken = [zone for zone in zones if not _is_effectively_broken_resistance(zone, daily_bars)]
    merged = _merge_nearby_resistances(unbroken, daily_atr)
    return _apply_congestion_zone_filter(merged, daily_atr)


def filter_current_daily_zones(
    zones: list[PriceZone],
    current_price: float,
) -> list[PriceZone]:
    return [_filter_current_zone(_copy_zone(zone), current_price) for zone in zones]


def is_hidden_display_zone(zone: PriceZone) -> bool:
    return "display_hidden" in zone.tags or "inner_congestion_zone" in zone.tags


def is_congestion_zone(zone: PriceZone) -> bool:
    return "congestion_zone" in zone.tags


def _filter_current_zone(zone: PriceZone, current_price: float) -> PriceZone:
    if "resistance" not in zone.tags or current_price <= 0:
        return zone

    distance_pct = _distance_to_zone(current_price, zone) / current_price
    standalone_fibonacci = "daily_fibonacci" in zone.tags and not _has_confluence(zone)
    if standalone_fibonacci:
        zone.level = ZoneLevel.D
        zone.tags = sorted(set(zone.tags + ["display_only_fibonacci"]))
        return zone

    if distance_pct > 0.35 and not _is_weekly_ab_resistance(zone):
        zone.level = ZoneLevel.D
        zone.tags = sorted(set(zone.tags + ["display_only_far_resistance"]))
        return zone
    if distance_pct > 0.20 and not _is_weekly_ab_resistance(zone):
        zone.level = _downgrade_one_level(zone.level)
        zone.tags = sorted(set(zone.tags + ["far_resistance_downgraded"]))

    if zone.level == ZoneLevel.C and not _is_valid_c_resistance(zone, distance_pct):
        zone.level = ZoneLevel.D
        zone.tags = sorted(set(zone.tags + ["weak_c_resistance"]))
    return zone


def _is_effectively_broken_resistance(zone: PriceZone, daily_bars: list[Bar]) -> bool:
    if "resistance" not in zone.tags:
        return False
    threshold = zone.invalidation_price if zone.invalidation_price is not None else zone.high
    if threshold <= 0:
        return False
    last_touch_idx = _last_touch_index(zone, daily_bars)
    if last_touch_idx is None:
        return False
    bars_after_touch = daily_bars[last_touch_idx + 1:]
    for prev, last in zip(bars_after_touch, bars_after_touch[1:]):
        if prev.close > threshold and last.close > threshold:
            return True
    return False


def _last_touch_index(zone: PriceZone, daily_bars: list[Bar]) -> int | None:
    for idx in range(len(daily_bars) - 1, -1, -1):
        bar = daily_bars[idx]
        if bar.high >= zone.low and bar.low <= zone.high:
            return idx
    return None


def _merge_nearby_resistances(zones: list[PriceZone], daily_atr: float) -> list[PriceZone]:
    merge_gap = max(daily_atr * 0.5, 0.0)
    supports = [zone for zone in zones if "resistance" not in zone.tags]
    resistances = sorted([zone for zone in zones if "resistance" in zone.tags], key=lambda item: item.low)
    merged: list[PriceZone] = []
    for zone in resistances:
        if merged and zone.low <= merged[-1].high + merge_gap:
            merged[-1] = _merge_resistance(merged[-1], zone)
            continue
        merged.append(zone)
    return sorted(supports + merged, key=lambda zone: (zone.level, zone.low))


def _apply_congestion_zone_filter(zones: list[PriceZone], daily_atr: float) -> list[PriceZone]:
    clusters = _find_congestion_clusters(zones, daily_atr)
    if not clusters:
        return zones

    congestion_zones: list[PriceZone] = []
    updated: list[PriceZone] = []
    original_by_index = {idx: zone for idx, zone in enumerate(zones)}
    rewritten_by_index: dict[int, PriceZone] = {}

    for cluster_idx, cluster in enumerate(clusters):
        members = [original_by_index[idx] for idx in cluster]
        envelope_low = min(zone.low for zone in members)
        envelope_high = max(zone.high for zone in members)
        span = max(envelope_high - envelope_low, 1e-9)
        supports = [zone for zone in members if "support" in zone.tags]
        resistances = [zone for zone in members if "resistance" in zone.tags]
        primary_support = _select_primary_support(supports, envelope_low)
        primary_resistance = _select_primary_resistance(resistances, envelope_high)

        congestion_level = min(
            [zone.level for zone in members],
            key=_level_rank,
        )
        congestion_score = max(zone.score for zone in members)
        congestion_importance = max(zone.importance_score for zone in members)
        congestion_fragility = max(zone.fragility_score for zone in members) + 1
        congestion_tags = [
            "congestion_zone",
            "mixed_congestion",
            "higher_conflict",
            "support",
            "resistance",
        ]
        if any("weekly_resistance" in zone.tags for zone in members):
            congestion_tags.append("with_weekly_resistance")
        congestion_zones.append(
            PriceZone(
                name=f"daily_congestion_{cluster_idx}",
                timeframe="mixed" if len({zone.timeframe for zone in members}) > 1 else members[0].timeframe,
                low=envelope_low,
                high=envelope_high,
                score=congestion_score,
                level=congestion_level,
                tags=sorted(set(congestion_tags)),
                touches=max(zone.touches for zone in members),
                importance_score=congestion_importance,
                fragility_score=congestion_fragility,
                invalidation_price=max(
                    [
                        value
                        for value in (
                            zone.invalidation_price for zone in members
                        )
                        if value is not None
                    ],
                    default=None,
                ),
            )
        )

        for idx in cluster:
            zone = _copy_zone(original_by_index[idx])
            zone.tags = sorted(set(zone.tags + ["congestion_member"]))
            if primary_support is not None and zone.name == primary_support.name:
                zone.tags = sorted(set(zone.tags + ["primary_congestion_support"]))
            if primary_resistance is not None and zone.name == primary_resistance.name:
                zone.tags = sorted(set(zone.tags + ["primary_congestion_resistance"]))

            is_primary = (
                (primary_support is not None and zone.name == primary_support.name)
                or (primary_resistance is not None and zone.name == primary_resistance.name)
            )
            near_lower_edge = (zone.low - envelope_low) <= span * 0.12
            near_upper_edge = (envelope_high - zone.high) <= span * 0.12
            if not is_primary and not near_lower_edge and not near_upper_edge:
                zone.tags = sorted(set(zone.tags + ["inner_congestion_zone", "display_hidden"]))
            rewritten_by_index[idx] = zone

    for idx, zone in enumerate(zones):
        updated.append(rewritten_by_index.get(idx, zone))

    return sorted(updated + congestion_zones, key=lambda zone: (zone.level, zone.low))


def _merge_resistance(left: PriceZone, right: PriceZone) -> PriceZone:
    best_level = _best_level(left.level, right.level)
    invalidation_candidates = [
        value for value in [left.invalidation_price, right.invalidation_price, left.high, right.high] if value is not None
    ]
    return PriceZone(
        name=f"{left.name}+{right.name}",
        timeframe=left.timeframe if left.timeframe == right.timeframe else "mixed",
        low=min(left.low, right.low),
        high=max(left.high, right.high),
        score=max(left.score, right.score),
        level=best_level,
        tags=sorted(set(left.tags + right.tags + ["merged_resistance"])),
        touches=max(left.touches, right.touches),
        importance_score=max(left.importance_score, right.importance_score),
        fragility_score=max(left.fragility_score, right.fragility_score),
        invalidation_price=max(invalidation_candidates) if invalidation_candidates else None,
    )


def _find_congestion_clusters(zones: list[PriceZone], daily_atr: float) -> list[list[int]]:
    indexed = [
        (idx, zone)
        for idx, zone in enumerate(zones)
        if zone.level in {ZoneLevel.A, ZoneLevel.B, ZoneLevel.C}
        and ("support" in zone.tags or "resistance" in zone.tags)
    ]
    if len(indexed) < 3:
        return []

    proximity_gap = max(daily_atr * 0.35, 0.0)
    adjacency: dict[int, set[int]] = {idx: set() for idx, _ in indexed}
    for left_idx, left_zone in indexed:
        for right_idx, right_zone in indexed:
            if left_idx >= right_idx:
                continue
            if _zones_are_clustered(left_zone, right_zone, proximity_gap):
                adjacency[left_idx].add(right_idx)
                adjacency[right_idx].add(left_idx)

    clusters: list[list[int]] = []
    visited: set[int] = set()
    for idx, _ in indexed:
        if idx in visited:
            continue
        stack = [idx]
        component: list[int] = []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            stack.extend(adjacency[current] - visited)
        if _qualifies_as_congestion(component, zones, daily_atr):
            clusters.append(sorted(component, key=lambda item: zones[item].low))
    return clusters


def _zones_are_clustered(left: PriceZone, right: PriceZone, proximity_gap: float) -> bool:
    if left.overlaps(right):
        return True
    return min(abs(right.low - left.high), abs(left.low - right.high)) <= proximity_gap


def _qualifies_as_congestion(cluster: list[int], zones: list[PriceZone], daily_atr: float) -> bool:
    if len(cluster) < 3:
        return False
    members = [zones[idx] for idx in cluster]
    supports = [zone for zone in members if "support" in zone.tags]
    resistances = [zone for zone in members if "resistance" in zone.tags]
    if not supports or not resistances:
        return False

    overlap_pairs = 0
    for support in supports:
        for resistance in resistances:
            if support.overlaps(resistance):
                overlap_pairs += 1
    if overlap_pairs == 0:
        return False

    span = max(zone.high for zone in members) - min(zone.low for zone in members)
    reference_price = max((zone.low + zone.high) / 2 for zone in members)
    max_span = max(daily_atr * 8, reference_price * 0.18)
    return span <= max_span


def _select_primary_support(supports: list[PriceZone], envelope_low: float) -> PriceZone | None:
    if not supports:
        return None
    return min(
        supports,
        key=lambda zone: (
            abs(zone.low - envelope_low),
            _level_rank(zone.level),
            -zone.score,
            -zone.importance_score,
        ),
    )


def _select_primary_resistance(resistances: list[PriceZone], envelope_high: float) -> PriceZone | None:
    if not resistances:
        return None
    return min(
        resistances,
        key=lambda zone: (
            abs(envelope_high - zone.high),
            _level_rank(zone.level),
            -zone.score,
            -zone.importance_score,
        ),
    )


def _is_valid_c_resistance(zone: PriceZone, distance_pct: float) -> bool:
    return distance_pct <= 0.08 or _has_confluence(zone) or "weekly_resistance" in zone.tags


def _has_confluence(zone: PriceZone) -> bool:
    confluence_tags = {
        "with_weekly_resistance",
        "with_fvg",
        "with_liquidity",
        "with_large_liquidity",
        "with_fibonacci",
        "with_order_block",
    }
    return bool(set(zone.tags) & confluence_tags)


def _is_weekly_ab_resistance(zone: PriceZone) -> bool:
    return "weekly_resistance" in zone.tags and zone.level in {ZoneLevel.A, ZoneLevel.B}


def _downgrade_one_level(level: ZoneLevel) -> ZoneLevel:
    if level == ZoneLevel.A:
        return ZoneLevel.B
    if level == ZoneLevel.B:
        return ZoneLevel.C
    return ZoneLevel.D


def _best_level(left: ZoneLevel, right: ZoneLevel) -> ZoneLevel:
    return min(left, right, key=_level_rank)


def _level_rank(level: ZoneLevel) -> int:
    if level == ZoneLevel.A:
        return 0
    if level == ZoneLevel.B:
        return 1
    if level == ZoneLevel.C:
        return 2
    return 3


def _distance_to_zone(price: float, zone: PriceZone) -> float:
    if zone.contains(price):
        return 0.0
    if price < zone.low:
        return zone.low - price
    return price - zone.high


def _copy_zone(zone: PriceZone) -> PriceZone:
    return PriceZone(
        name=zone.name,
        timeframe=zone.timeframe,
        low=zone.low,
        high=zone.high,
        score=zone.score,
        level=zone.level,
        tags=list(zone.tags),
        touches=zone.touches,
        importance_score=zone.importance_score,
        fragility_score=zone.fragility_score,
        invalidation_price=zone.invalidation_price,
    )
