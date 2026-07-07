from __future__ import annotations

from sell_monitor.domain.enums import Action, Priority, ZoneLevel
from sell_monitor.domain.models import Bar, DailyContext, Decision, PriceZone, Signal
from sell_monitor.indicators.atr import compute_atr
from sell_monitor.indicators.ma import closing_ma
from sell_monitor.indicators.volume_stats import average_volume
from sell_monitor.zones.daily_zone_filter import is_hidden_display_zone


UNFILTERABLE_SIGNAL_NAMES = {
    "breakout_failure",
    "trendline_break",
    "structure_break",
    "m15_ma20_high_volume_break",
    "open_20min_risk",
    "high_volume_drop_below_ma5",
}


def apply_support_protection(
    decision: Decision,
    daily_context: DailyContext,
    daily_bars: list[Bar],
    m15_bars: list[Bar],
    signals: list[Signal],
) -> Decision:
    if decision.action != Action.REDUCE:
        return decision
    if _has_unfilterable_risk(signals, m15_bars):
        return decision

    support = find_protective_daily_support(daily_context.current_price, daily_context.daily_zones, daily_bars)
    if support is None:
        return decision

    return Decision(
        symbol=decision.symbol,
        action=Action.HOLD,
        total_score=min(decision.total_score, 3),
        priority=Priority.NORMAL,
        reasons=decision.reasons
        + [
            f"强支撑保护过滤：当前仍位于日线{support.level.value}级支撑区 {support.low:.2f}-{support.high:.2f} 上方，普通减仓信号降级为观察"
        ],
        next_step="支撑保护区上方暂不减仓，继续观察；若放量跌破支撑或15分钟MA20，再重新评估卖出",
        cancel_condition="跌破日线A/B级支撑区下沿，或出现第三根危险上影线、突破失败、放量跌破15分钟MA20",
        symbol_name=decision.symbol_name,
        current_price=decision.current_price,
    )


def apply_exit_support_protection(
    decision: Decision,
    daily_context: DailyContext,
    daily_bars: list[Bar],
) -> Decision:
    if decision.action != Action.EXIT_ALL:
        return decision
    if not any("危险上影线" in reason for reason in decision.reasons):
        return decision

    support = find_protective_daily_support(daily_context.current_price, daily_context.daily_zones, daily_bars)
    if support is None:
        return decision

    return Decision(
        symbol=decision.symbol,
        action=Action.REDUCE,
        total_score=5,
        priority=Priority.HIGH,
        reasons=decision.reasons
        + [
            f"强支撑保护过滤：当前仍位于日线{support.level.value}级支撑区 {support.low:.2f}-{support.high:.2f} 上方，第三根上影线清仓信号降级为减仓"
        ],
        next_step="先减仓50%；若放量跌破日线A/B级支撑区下沿或15分钟MA20无法收回，再执行清仓",
        cancel_condition="价格继续站稳日线A/B级支撑区和15分钟MA20，且危险上影线信号不再延续",
        symbol_name=decision.symbol_name,
        current_price=decision.current_price,
    )


def apply_a_level_support_bias_filter(
    decision: Decision,
    daily_context: DailyContext,
) -> Decision:
    if decision.action not in {Action.REDUCE, Action.EXIT_ALL}:
        return decision
    if any("用户设置了硬性清仓规则" in reason for reason in decision.reasons):
        return decision

    bias = find_ab_level_support_bias(daily_context.current_price, daily_context.daily_zones)
    if bias is None:
        return decision

    support, resistance, support_distance, resistance_distance = bias
    support_level = support.level.value
    resistance_level = resistance.level.value
    return Decision(
        symbol=decision.symbol,
        action=Action.HOLD,
        total_score=min(decision.total_score, 3),
        priority=Priority.NORMAL,
        reasons=decision.reasons
        + [
            f"{support_level}级支撑偏置过滤：当前价未跌破日线{support_level}级支撑区 {support.low:.2f}-{support.high:.2f}，距离支撑约 {support_distance:.2f}，距离日线{resistance_level}级压力区 {resistance.low:.2f}-{resistance.high:.2f} 约 {resistance_distance:.2f}，当前更靠近支撑，暂不报告该卖出动作"
        ],
        next_step=f"支撑上方继续观察；只有跌破该{support_level}级支撑区下沿，或重新靠近{resistance_level}级压力区并出现破位确认后再评估卖出",
        cancel_condition=f"跌破日线{support_level}级支撑区下沿，或价格更接近日线{resistance_level}级压力区",
        symbol_name=decision.symbol_name,
        current_price=decision.current_price,
    )


def find_a_level_support_bias(
    current_price: float,
    zones: list[PriceZone],
) -> tuple[PriceZone, PriceZone, float, float] | None:
    bias = find_ab_level_support_bias(current_price, zones)
    if bias and bias[0].level == ZoneLevel.A:
        return bias
    return None


def find_ab_level_support_bias(
    current_price: float,
    zones: list[PriceZone],
) -> tuple[PriceZone, PriceZone, float, float] | None:
    if current_price <= 0:
        return None
    supports = [
        zone
        for zone in zones
        if "support" in zone.tags
        and zone.level in {ZoneLevel.A, ZoneLevel.B}
        and not is_hidden_display_zone(zone)
        and current_price >= _support_invalidation_price(zone)
        and _support_is_actionable(current_price, zone)
    ]
    resistances = [
        zone
        for zone in zones
        if "resistance" in zone.tags
        and zone.level in {ZoneLevel.A, ZoneLevel.B, ZoneLevel.C}
        and not is_hidden_display_zone(zone)
        and current_price <= zone.high
    ]
    if not supports or not resistances:
        return None
    support = min(supports, key=lambda zone: (_distance_to_zone(current_price, zone), _level_rank(zone.level), -zone.score))
    resistance = min(
        resistances,
        key=lambda zone: (_distance_to_zone(current_price, zone), _level_rank(zone.level), -zone.score),
    )
    support_distance = _distance_to_zone(current_price, support)
    resistance_distance = _distance_to_zone(current_price, resistance)
    if support_distance < resistance_distance:
        return support, resistance, support_distance, resistance_distance
    return None


def find_protective_daily_support(current_price: float, zones: list[PriceZone], daily_bars: list[Bar]) -> PriceZone | None:
    if current_price <= 0:
        return None
    atr14 = compute_atr(daily_bars, 14)
    protection_pad = max(current_price * 0.03, atr14 * 1.2)
    supports = [
        zone
        for zone in zones
        if "support" in zone.tags
        and zone.level in {ZoneLevel.A, ZoneLevel.B}
        and not is_hidden_display_zone(zone)
        and _support_is_actionable(current_price, zone)
        and _support_invalidation_price(zone) <= current_price <= zone.high + protection_pad
    ]
    if not supports:
        return None
    return max(supports, key=lambda zone: (zone.level == ZoneLevel.A, zone.score, zone.high))


def _support_invalidation_price(zone: PriceZone) -> float:
    return zone.invalidation_price if zone.invalidation_price is not None else zone.low


def _support_is_actionable(current_price: float, zone: PriceZone) -> bool:
    if "primary_congestion_support" not in zone.tags:
        return True
    span = max(zone.high - zone.low, 1e-9)
    buffer = max(span * 0.8, current_price * 0.015)
    return current_price <= zone.high + buffer


def _distance_to_zone(price: float, zone: PriceZone) -> float:
    if zone.contains(price):
        return 0.0
    if price < zone.low:
        return zone.low - price
    return price - zone.high


def _level_rank(level: ZoneLevel) -> int:
    if level == ZoneLevel.A:
        return 0
    if level == ZoneLevel.B:
        return 1
    if level == ZoneLevel.C:
        return 2
    return 3


def _has_unfilterable_risk(signals: list[Signal], m15_bars: list[Bar]) -> bool:
    names = {signal.name for signal in signals if signal.triggered}
    if names & UNFILTERABLE_SIGNAL_NAMES:
        return True
    return _is_high_volume_break_below_m15_ma20(m15_bars)


def _is_high_volume_break_below_m15_ma20(m15_bars: list[Bar]) -> bool:
    if len(m15_bars) < 21:
        return False
    last = m15_bars[-1]
    prev_ma20 = closing_ma(m15_bars[-21:-1], 20)
    avg_vol_10 = average_volume(m15_bars[-11:-1], 10)
    return prev_ma20 > 0 and last.close < prev_ma20 and avg_vol_10 > 0 and last.volume >= avg_vol_10 * 1.5
