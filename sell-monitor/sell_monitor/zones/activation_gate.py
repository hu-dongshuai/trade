from __future__ import annotations

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import PriceZone


def find_active_zone(current_price: float, daily_atr: float, zones: list[PriceZone]) -> PriceZone | None:
    candidates = [zone for zone in zones if zone.level in {ZoneLevel.A, ZoneLevel.B}]
    if not candidates:
        return None
    threshold_pad = max(daily_atr * 0.5, current_price * 0.01)
    ranked = sorted(candidates, key=lambda zone: (zone.level.value, abs(zone.low - current_price)))
    for zone in ranked:
        if zone.low - threshold_pad <= current_price <= zone.high + threshold_pad:
            return zone
    return None

