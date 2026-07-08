from __future__ import annotations

from sell_monitor.domain.models import Bar, DailyContext, Signal
from sell_monitor.indicators.ma import closing_ma
from sell_monitor.indicators.rsi import has_bearish_rsi_divergence
from sell_monitor.indicators.volume_stats import average_volume
from sell_monitor.signals.breakout_failure import detect_breakout_failure
from sell_monitor.signals.dangerous_upper_wick import detect_dangerous_upper_wick_signals
from sell_monitor.signals.gap_risk import detect_gap_risk
from sell_monitor.signals.liquidity_grab import detect_resistance_liquidity_grab
from sell_monitor.signals.m60_bearish_confirmation import detect_m60_bearish_confirmation
from sell_monitor.signals.open_20min_risk import detect_open_20min_risk
from sell_monitor.signals.structure_break import detect_structure_break
from sell_monitor.signals.trendline_break import detect_trendline_break
from sell_monitor.signals.volume_price_anomaly import detect_volume_price_anomaly
from sell_monitor.zones.intraday_zone_detector import detect_intraday_resistance_near_active_zone


def run_intraday_monitor(daily_context: DailyContext, daily_bars, m15_bars) -> list[Signal]:
    warning_mode = daily_context.sell_warning_active and daily_context.active_zone is None
    if not daily_context.active_zone and not warning_mode:
        return []

    signals: list[Signal] = []
    active_zone = daily_context.active_zone
    support_only_zone = False

    if warning_mode:
        last_bar = m15_bars[-1]
        warning_reason = "已进入日线/60分钟转弱预警态：" + "；".join(daily_context.sell_warning_reasons[:2])
        signals.append(
            Signal(
                "sell_warning_state",
                1,
                True,
                warning_reason,
                triggered_at=last_bar.ts,
                trigger_price=last_bar.close,
            )
        )

    if active_zone is not None:
        detect_intraday_resistance_near_active_zone(m15_bars, active_zone)
        support_only_zone = "support" in active_zone.tags and "resistance" not in active_zone.tags

        if not support_only_zone and has_bearish_rsi_divergence(m15_bars):
            last_bar = m15_bars[-1]
            signals.append(
                Signal(
                    "rsi_bearish_divergence",
                    1,
                    True,
                    "RSI 顶背离且位于关键价位附近",
                    triggered_at=last_bar.ts,
                    trigger_price=last_bar.close,
                )
            )

        if not support_only_zone:
            signals.extend(detect_dangerous_upper_wick_signals(m15_bars, active_zone))
            breakout_failure = detect_breakout_failure(m15_bars, active_zone)
            if breakout_failure:
                signals.append(breakout_failure)
            liquidity_grab = detect_resistance_liquidity_grab(m15_bars, active_zone)
            if liquidity_grab:
                signals.append(liquidity_grab)

    trendline_break = detect_trendline_break(m15_bars)
    if trendline_break:
        signals.append(trendline_break)

    structure_break = detect_structure_break(m15_bars)
    if structure_break:
        signals.append(structure_break)

    gap_risk = detect_gap_risk(daily_bars)
    if gap_risk:
        signals.append(gap_risk)

    open_risk = detect_open_20min_risk(m15_bars)
    if open_risk:
        signals.append(open_risk)

    ma20_break = detect_m15_ma20_high_volume_break(m15_bars)
    if ma20_break:
        signals.append(ma20_break)

    m60_bearish = detect_m60_bearish_confirmation(m15_bars)
    if m60_bearish:
        signals.append(m60_bearish)

    signals.extend(detect_volume_price_anomaly(m15_bars, daily_bars))

    if daily_context.market_state == "down":
        last_bar = m15_bars[-1]
        signals.append(
            Signal(
                "market_weakness",
                1,
                True,
                "大盘同步转弱",
                triggered_at=last_bar.ts,
                trigger_price=last_bar.close,
            )
        )

    if active_zone is not None and not support_only_zone and daily_context.active_zone.level.value == "A":
        last_bar = m15_bars[-1]
        signals.append(
            Signal(
                "a_level_zone",
                1,
                True,
                "当前位于 A 级日线关键价位附近",
                triggered_at=last_bar.ts,
                trigger_price=last_bar.close,
            )
        )

    return signals


def detect_m15_ma20_high_volume_break(m15_bars: list[Bar]) -> Signal | None:
    if len(m15_bars) < 22:
        return None

    prev = m15_bars[-2]
    last = m15_bars[-1]
    prev_ma20 = closing_ma(m15_bars[-22:-2], 20)
    last_ma20 = closing_ma(m15_bars[-21:-1], 20)
    avg_vol_10 = average_volume(m15_bars[-11:-1], 10)

    if (
        prev_ma20 > 0
        and last_ma20 > 0
        and prev.close < prev_ma20
        and last.close < last_ma20
        and avg_vol_10 > 0
        and last.volume >= avg_vol_10 * 1.5
    ):
        return Signal(
            "m15_ma20_high_volume_break",
            2,
            True,
            f"{last.ts:%H:%M} 这根15分钟K线放量，且连续两根15分钟K线收在 MA20 下方",
            triggered_at=last.ts,
            trigger_price=last.close,
        )
    return None
