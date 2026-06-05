from __future__ import annotations

from sell_monitor.domain.models import Bar, DailyContext, Decision, PriceZone
from sell_monitor.indicators.volume_stats import average_volume
from sell_monitor.scoring.support_protection import find_ab_level_support_bias, find_protective_daily_support


def apply_hold_protection_reference(
    decision: Decision,
    daily_context: DailyContext,
    daily_bars: list[Bar],
    m15_bars: list[Bar],
) -> Decision:
    score = 0
    reasons: list[str] = []

    support = find_protective_daily_support(daily_context.current_price, daily_context.daily_zones, daily_bars)
    if support is not None:
        support_score = 2 if support.level.value == "A" else 1
        score += support_score
        reasons.append(
            f"日线{support.level.value}级支撑保护：当前仍位于支撑区 {support.low:.2f}-{support.high:.2f} 上方，持有保护分 +{support_score}"
        )

    bias = find_ab_level_support_bias(daily_context.current_price, daily_context.daily_zones)
    if bias is not None:
        support_zone, resistance_zone, support_distance, resistance_distance = bias
        score += 1
        reasons.append(
            "支撑距离优势："
            f"当前距离日线{support_zone.level.value}级支撑区 {support_zone.low:.2f}-{support_zone.high:.2f} "
            f"约 {support_distance:.2f}，距离日线{resistance_zone.level.value}级压力区 "
            f"{resistance_zone.low:.2f}-{resistance_zone.high:.2f} 约 {resistance_distance:.2f}，持有保护分 +1"
        )

    sweep_signal = detect_support_liquidity_grab_reclaim(m15_bars, daily_context.daily_zones)
    if sweep_signal is not None:
        score += sweep_signal[0]
        reasons.append(sweep_signal[1])

    return Decision(
        symbol=decision.symbol,
        action=decision.action,
        total_score=decision.total_score,
        priority=decision.priority,
        reasons=decision.reasons,
        next_step=decision.next_step,
        cancel_condition=decision.cancel_condition,
        symbol_name=decision.symbol_name,
        current_price=decision.current_price,
        hold_protection_score=score,
        hold_protection_reasons=reasons,
    )


def detect_support_liquidity_grab_reclaim(
    bars: list[Bar],
    zones: list[PriceZone],
) -> tuple[int, str] | None:
    if len(bars) < 12:
        return None
    supports = [zone for zone in zones if "support" in zone.tags and zone.level.value in {"A", "B"}]
    if not supports:
        return None
    recent_start = max(10, len(bars) - 4)
    for idx in range(recent_start, len(bars)):
        bar = bars[idx]
        avg_vol = average_volume(bars[idx - 10:idx], 10)
        if avg_vol <= 0:
            continue
        for zone in supports:
            swept_below_support = bar.low < zone.low
            reclaimed_support = bar.close >= zone.low
            volume_confirms = bar.volume >= avg_vol * 1.2
            lower_wick_ratio = bar.lower_wick / bar.range if bar.range > 0 else 0.0
            if swept_below_support and reclaimed_support and volume_confirms and lower_wick_ratio >= 0.35:
                bonus = 2 if zone.level.value == "A" else 1
                return (
                    bonus,
                    f"向下流动性抓取后收回支撑：15分钟K线下探日线{zone.level.value}级支撑区 "
                    f"{zone.low:.2f}-{zone.high:.2f} 后收回，且成交量放大，持有保护分 +{bonus}",
                )
    return None
