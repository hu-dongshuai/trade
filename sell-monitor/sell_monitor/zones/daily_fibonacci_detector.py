from __future__ import annotations

from sell_monitor.domain.enums import ZoneLevel
from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.indicators.atr import compute_atr
from sell_monitor.indicators.swing_points import find_swing_highs, find_swing_lows


RETRACEMENT_RATIOS = (0.382, 0.5, 0.618, 0.786)
EXTENSION_RATIOS = (1.272, 1.618)


def detect_daily_fibonacci_resistance_zones(bars: list[Bar]) -> list[PriceZone]:
    if len(bars) < 30:
        return []
    latest_close = bars[-1].close
    atr = compute_atr(bars, 14)
    half_width = max(atr * 0.15, latest_close * 0.004)
    zones: list[PriceZone] = []

    down_leg = _latest_down_leg(bars)
    if down_leg:
        high_idx, high, low_idx, low = down_leg
        width = high - low
        for ratio in RETRACEMENT_RATIOS:
            level = low + width * ratio
            if _is_relevant_resistance(level, latest_close):
                zones.append(
                    _fib_zone(
                        name=f"daily_fib_retracement_{ratio:g}_{high_idx}_{low_idx}",
                        level=level,
                        half_width=half_width,
                        tag=f"fib_{ratio:g}",
                    )
                )

    up_leg = _latest_up_leg(bars)
    if up_leg:
        low_idx, low, high_idx, high = up_leg
        width = high - low
        for ratio in EXTENSION_RATIOS:
            level = high + width * (ratio - 1.0)
            if _is_relevant_resistance(level, latest_close):
                zones.append(
                    _fib_zone(
                        name=f"daily_fib_extension_{ratio:g}_{low_idx}_{high_idx}",
                        level=level,
                        half_width=half_width,
                        tag=f"fib_ext_{ratio:g}",
                    )
                )
    return _dedupe_fib_zones(zones)


def _fib_zone(name: str, level: float, half_width: float, tag: str) -> PriceZone:
    return PriceZone(
        name=name,
        timeframe="1d",
        low=level - half_width,
        high=level + half_width,
        score=3,
        level=ZoneLevel.C,
        tags=["resistance", "daily_fibonacci", tag],
        touches=0,
        importance_score=3,
        fragility_score=0,
        invalidation_price=level + half_width,
    )


def _latest_down_leg(bars: list[Bar]) -> tuple[int, float, int, float] | None:
    highs = find_swing_highs(bars)
    lows = find_swing_lows(bars)
    for low_idx, low_bar in reversed(lows):
        prior_highs = [(idx, bar) for idx, bar in highs if idx < low_idx]
        if not prior_highs:
            continue
        high_idx, high_bar = max(prior_highs[-8:], key=lambda item: item[1].high)
        if high_bar.high > low_bar.low * 1.08:
            return high_idx, high_bar.high, low_idx, low_bar.low
    return None


def _latest_up_leg(bars: list[Bar]) -> tuple[int, float, int, float] | None:
    highs = find_swing_highs(bars)
    lows = find_swing_lows(bars)
    for high_idx, high_bar in reversed(highs):
        prior_lows = [(idx, bar) for idx, bar in lows if idx < high_idx]
        if not prior_lows:
            continue
        low_idx, low_bar = min(prior_lows[-8:], key=lambda item: item[1].low)
        if high_bar.high > low_bar.low * 1.08:
            return low_idx, low_bar.low, high_idx, high_bar.high
    return None


def _is_relevant_resistance(level: float, latest_close: float) -> bool:
    return latest_close * 0.90 <= level <= latest_close * 1.35


def _dedupe_fib_zones(zones: list[PriceZone]) -> list[PriceZone]:
    result: list[PriceZone] = []
    for zone in sorted(zones, key=lambda item: item.low):
        if result and zone.low <= result[-1].high:
            previous = result[-1]
            previous.low = min(previous.low, zone.low)
            previous.high = max(previous.high, zone.high)
            previous.tags = sorted(set(previous.tags + zone.tags))
            previous.name = f"{previous.name}+{zone.name}"
            previous.invalidation_price = max(previous.invalidation_price or previous.high, zone.invalidation_price or zone.high)
            continue
        result.append(zone)
    return result
