from __future__ import annotations

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import PriceZone
from sell_monitor.zones.daily_zone_filter import is_congestion_zone, is_hidden_display_zone


def find_active_zone(current_price: float, daily_atr: float, zones: list[PriceZone]) -> PriceZone | None:
    if _price_in_congestion_mid(current_price, daily_atr, zones):
        return None
    candidates = [
        zone
        for zone in zones
        if not is_hidden_display_zone(zone)
        and not is_congestion_zone(zone)
        if zone.level in {ZoneLevel.A, ZoneLevel.B}
        or (zone.level == ZoneLevel.C and "resistance" in zone.tags)
    ]
    if not candidates:
        return None
    threshold_pad = max(daily_atr * 0.5, current_price * 0.01)
    ranked = sorted(
        candidates,
        key=lambda zone: (
            _distance_to_zone(current_price, zone),
            _zone_width(zone),
            zone.level.value,
            "resistance" not in zone.tags,
        ),
    )
    for zone in ranked:
        if zone.low - threshold_pad <= current_price <= zone.high + threshold_pad:
            return zone
    return None


def _price_in_congestion_mid(current_price: float, daily_atr: float, zones: list[PriceZone]) -> bool:
    for zone in zones:
        if not is_congestion_zone(zone) or not zone.contains(current_price):
            continue
        span = max(zone.high - zone.low, 1e-9)
        edge_pad = max(span * 0.22, daily_atr * 0.6)
        if zone.low + edge_pad < current_price < zone.high - edge_pad:
            return True
    return False


def _distance_to_zone(price: float, zone: PriceZone) -> float:
    if zone.contains(price):
        return 0.0
    if price < zone.low:
        return zone.low - price
    return price - zone.high


def _zone_width(zone: PriceZone) -> float:
    return max(zone.high - zone.low, 0.0)
