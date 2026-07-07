from __future__ import annotations

from datetime import datetime

from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.indicators.ma import closing_ma
from sell_monitor.zones.daily_fvg_detector import detect_daily_fvg
from sell_monitor.zones.daily_liquidity_detector import detect_daily_liquidity_zones
from sell_monitor.zones.daily_order_block_detector import detect_daily_order_blocks
from sell_monitor.zones.daily_sr_detector import detect_daily_sr_zones
from sell_monitor.zones.daily_zone_ranker import rank_daily_zones


def build_weekly_entry_view(
    daily_bars: list[Bar],
    current_price: float,
    is_m60_trend_healthy: bool,
) -> tuple[list[PriceZone], list[PriceZone], str, int, list[str]]:
    weekly_bars = _to_weekly_bars(daily_bars)
    if len(weekly_bars) < 12:
        reasons = ["周线样本不足，当前按中性周线背景处理"]
        score = 2 if is_m60_trend_healthy else 0
        return [], [], "B", score, reasons

    weekly_zones = rank_daily_zones(
        detect_daily_sr_zones(weekly_bars),
        detect_daily_fvg(weekly_bars),
        detect_daily_liquidity_zones(weekly_bars),
        detect_daily_order_blocks(weekly_bars),
    )
    weekly_support_zones = [zone for zone in weekly_zones if "support" in zone.tags]
    weekly_resistance_zones = [zone for zone in weekly_zones if "resistance" in zone.tags]
    for zone in weekly_zones:
        zone.timeframe = "1w"
        zone.name = zone.name.replace("daily_", "weekly_", 1) if zone.name.startswith("daily_") else f"weekly_{zone.name}"
        if "higher_timeframe" not in zone.tags:
            zone.tags.append("higher_timeframe")

    weekly_ma20 = closing_ma(weekly_bars, 20) if len(weekly_bars) >= 20 else 0.0
    weekly_trend_healthy = weekly_ma20 <= 0 or current_price >= weekly_ma20
    nearest_support = _nearest_zone_below(current_price, weekly_support_zones, max_distance_pct=0.05)
    nearest_resistance = _nearest_zone_above(current_price, weekly_resistance_zones, max_distance_pct=0.10)
    near_support = nearest_support is not None and _is_near_zone(current_price, nearest_support, 0.04)
    near_resistance = nearest_resistance is not None and _is_near_zone(current_price, nearest_resistance, 0.08)

    reasons: list[str] = []
    score = 0

    if near_support:
        score += 2
        reasons.append(
            f"周线接近{nearest_support.level.value}级支撑区 {nearest_support.low:.2f}-{nearest_support.high:.2f}"
        )
    if not near_resistance:
        score += 1
        reasons.append("周线上方未紧贴高等级压力，位置容错更高")
    else:
        reasons.append(
            f"周线上方存在{nearest_resistance.level.value}级压力区 {nearest_resistance.low:.2f}-{nearest_resistance.high:.2f}"
        )
    if _weekly_volume_contracts(weekly_bars):
        score += 1
        reasons.append("周线近几周量能收缩，符合中继整理特征")
    if _daily_false_break_reclaim(daily_bars):
        score += 2
        reasons.append("日线近几天出现假跌破后收回，偏向洗盘回收筹码")
    if _daily_higher_lows(daily_bars):
        score += 1
        reasons.append("日线低点逐步抬高，回踩重心未继续下移")
    if _daily_pullback_volume_healthy(daily_bars):
        score += 1
        reasons.append("日线回踩缩量，抛压未显著失控")
    if _obv_slope_up(daily_bars) and _ad_line_slope_up(daily_bars):
        score += 2
        reasons.append("量价累积代理指标改善，承接迹象增强")
    if is_m60_trend_healthy:
        score += 2
        reasons.append("60分钟结构保持抬升，中级别承接仍在")
    if _high_upper_wick_near_resistance(daily_bars, nearest_resistance):
        score -= 2
        reasons.append("近期日线高位上影偏长，存在压力位抛压")
    if _daily_breakdown_not_reclaimed(daily_bars):
        score -= 2
        reasons.append("日线破位后尚未有效收回，不宜按洗盘结构解读")

    score = max(0, min(10, score))

    if not weekly_trend_healthy and near_resistance:
        background = "C"
    elif not weekly_trend_healthy and not near_support:
        background = "C"
    elif near_support and weekly_trend_healthy and not near_resistance:
        background = "A"
    else:
        background = "B"

    return weekly_support_zones, weekly_resistance_zones, background, score, reasons


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


def _nearest_zone_below(price: float, zones: list[PriceZone], max_distance_pct: float) -> PriceZone | None:
    candidates = [zone for zone in zones if zone.low <= price and price - zone.high <= price * max_distance_pct]
    if not candidates:
        return None
    return min(candidates, key=lambda zone: abs(price - zone.high))


def _nearest_zone_above(price: float, zones: list[PriceZone], max_distance_pct: float) -> PriceZone | None:
    candidates = [zone for zone in zones if zone.high >= price and zone.low - price <= price * max_distance_pct]
    if not candidates:
        return None
    return min(candidates, key=lambda zone: max(zone.low - price, 0.0))


def _is_near_zone(price: float, zone: PriceZone, threshold_pct: float) -> bool:
    if zone.contains(price):
        return True
    gap = min(abs(price - zone.low), abs(price - zone.high))
    return gap / max(price, 0.01) <= threshold_pct


def _weekly_volume_contracts(weekly_bars: list[Bar]) -> bool:
    if len(weekly_bars) < 6:
        return False
    recent = weekly_bars[-3:]
    previous = weekly_bars[-6:-3]
    recent_avg = sum(bar.volume for bar in recent) / len(recent)
    previous_avg = sum(bar.volume for bar in previous) / len(previous)
    return recent_avg <= previous_avg * 0.90


def _daily_false_break_reclaim(daily_bars: list[Bar]) -> bool:
    if len(daily_bars) < 8:
        return False
    recent = daily_bars[-3:]
    prior_support = min(bar.low for bar in daily_bars[-8:-3])
    reclaim_bar = recent[-1]
    breakdown = min(bar.low for bar in recent) < prior_support * 0.995
    reclaim = reclaim_bar.close >= prior_support and reclaim_bar.close >= recent[-2].high
    return breakdown and reclaim


def _daily_higher_lows(daily_bars: list[Bar]) -> bool:
    if len(daily_bars) < 4:
        return False
    lows = [bar.low for bar in daily_bars[-4:]]
    return lows[-1] >= lows[-2] >= min(lows[:2])


def _daily_pullback_volume_healthy(daily_bars: list[Bar]) -> bool:
    if len(daily_bars) < 6:
        return False
    recent = daily_bars[-3:]
    previous = daily_bars[-6:-3]
    recent_avg = sum(bar.volume for bar in recent) / len(recent)
    previous_avg = sum(bar.volume for bar in previous) / len(previous)
    return recent_avg <= previous_avg


def _obv_slope_up(daily_bars: list[Bar], lookback: int = 20) -> bool:
    if len(daily_bars) < 3:
        return False
    sample = daily_bars[-lookback:]
    obv = 0.0
    values: list[float] = []
    for idx, bar in enumerate(sample):
        if idx == 0:
            values.append(obv)
            continue
        prev_close = sample[idx - 1].close
        if bar.close > prev_close:
            obv += bar.volume
        elif bar.close < prev_close:
            obv -= bar.volume
        values.append(obv)
    return values[-1] > values[0]


def _ad_line_slope_up(daily_bars: list[Bar], lookback: int = 20) -> bool:
    if len(daily_bars) < 3:
        return False
    sample = daily_bars[-lookback:]
    cumulative = 0.0
    values: list[float] = []
    for bar in sample:
        spread = max(bar.high - bar.low, 0.01)
        multiplier = ((bar.close - bar.low) - (bar.high - bar.close)) / spread
        cumulative += multiplier * bar.volume
        values.append(cumulative)
    return values[-1] > values[0]


def _high_upper_wick_near_resistance(daily_bars: list[Bar], resistance: PriceZone | None) -> bool:
    if resistance is None or len(daily_bars) < 3:
        return False
    last = daily_bars[-1]
    if last.high < resistance.low * 0.99:
        return False
    return last.upper_wick / max(last.range, 0.01) >= 0.45


def _daily_breakdown_not_reclaimed(daily_bars: list[Bar]) -> bool:
    if len(daily_bars) < 6:
        return False
    prior_support = min(bar.low for bar in daily_bars[-6:-2])
    last = daily_bars[-1]
    return last.close < prior_support and last.close <= daily_bars[-2].close
