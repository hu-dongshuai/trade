from __future__ import annotations

from sell_monitor.domain.models import Bar, DailyContext, Signal
from sell_monitor.indicators.ma import closing_ma
from sell_monitor.indicators.rsi import has_bearish_rsi_divergence
from sell_monitor.indicators.volume_stats import average_volume
from sell_monitor.signals.breakout_failure import detect_breakout_failure
from sell_monitor.signals.dangerous_upper_wick import detect_dangerous_upper_wick_signals
from sell_monitor.signals.gap_risk import detect_gap_risk
from sell_monitor.signals.open_20min_risk import detect_open_20min_risk
from sell_monitor.signals.structure_break import detect_structure_break
from sell_monitor.signals.trendline_break import detect_trendline_break
from sell_monitor.signals.volume_price_anomaly import detect_volume_price_anomaly
from sell_monitor.zones.intraday_zone_detector import detect_intraday_resistance_near_active_zone


def run_intraday_monitor(daily_context: DailyContext, daily_bars, m15_bars) -> list[Signal]:
    if not daily_context.active_zone:
        return []

    signals: list[Signal] = []
    active_zone = daily_context.active_zone
    detect_intraday_resistance_near_active_zone(m15_bars, active_zone)

    if has_bearish_rsi_divergence(m15_bars):
        signals.append(Signal("rsi_bearish_divergence", 1, True, "RSI顶背离且位于关键价位附近"))

    signals.extend(detect_dangerous_upper_wick_signals(m15_bars, active_zone))

    breakout_failure = detect_breakout_failure(m15_bars, active_zone)
    if breakout_failure:
        signals.append(breakout_failure)

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

    signals.extend(detect_volume_price_anomaly(m15_bars, daily_bars))

    if daily_context.market_state == "down":
        signals.append(Signal("market_weakness", 1, True, "大盘同步转弱"))
    if daily_context.active_zone.level.value == "A":
        signals.append(Signal("a_level_zone", 1, True, "当前位于A级日线关键价位附近"))
    return signals


def detect_m15_ma20_high_volume_break(m15_bars: list[Bar]) -> Signal | None:
    if len(m15_bars) < 21:
        return None
    last = m15_bars[-1]
    prev_ma20 = closing_ma(m15_bars[-21:-1], 20)
    avg_vol_10 = average_volume(m15_bars[-11:-1], 10)
    if prev_ma20 > 0 and last.close < prev_ma20 and avg_vol_10 > 0 and last.volume >= avg_vol_10 * 1.5:
        return Signal("m15_ma20_high_volume_break", 2, True, "放量跌破15分钟MA20")
    return None
