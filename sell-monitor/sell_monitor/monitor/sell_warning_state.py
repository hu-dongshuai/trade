from __future__ import annotations

from dataclasses import replace

from sell_monitor.domain.models import DailyContext
from sell_monitor.indicators.ma import closing_ma
from sell_monitor.indicators.timeframe import aggregate_m15_to_m60


def with_sell_warning_state(daily_context: DailyContext, m15_bars) -> DailyContext:
    active, reasons = evaluate_sell_warning_state(daily_context.daily_bars, m15_bars)
    return replace(
        daily_context,
        sell_warning_active=active,
        sell_warning_reasons=reasons,
    )


def evaluate_sell_warning_state(daily_bars, m15_bars) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if _daily_close_below_flat_ma20(daily_bars):
        reasons.append("日线收盘跌破 MA20，且 MA20 已走平或开始拐头")
    if _daily_failed_rebounds(daily_bars):
        reasons.append("日线最近两次反弹高点未能继续抬高")
    if _m60_structure_turns_down(m15_bars):
        reasons.append("60分钟结构转弱，出现更低高点和更低低点")
    if _m60_rebound_volume_weak(m15_bars):
        reasons.append("60分钟反弹量能弱于下跌量能，承接偏弱")
    return len(reasons) >= 2, reasons


def _daily_close_below_flat_ma20(daily_bars) -> bool:
    if len(daily_bars) < 25:
        return False
    ma20 = closing_ma(daily_bars[-20:], 20)
    prev_ma20 = closing_ma(daily_bars[-21:-1], 20)
    if ma20 <= 0 or prev_ma20 <= 0:
        return False
    last = daily_bars[-1]
    return last.close < ma20 and ma20 <= prev_ma20 * 1.002


def _daily_failed_rebounds(daily_bars) -> bool:
    if len(daily_bars) < 8:
        return False
    highs = [bar.high for bar in daily_bars[-8:]]
    return highs[-1] < max(highs[-4:-1]) and max(highs[-4:-1]) < max(highs[-7:-4])


def _m60_structure_turns_down(m15_bars) -> bool:
    m60_bars = aggregate_m15_to_m60(m15_bars)
    if len(m60_bars) < 6:
        return False
    last = m60_bars[-1]
    prev = m60_bars[-2]
    return last.high < prev.high and last.low < prev.low


def _m60_rebound_volume_weak(m15_bars) -> bool:
    m60_bars = aggregate_m15_to_m60(m15_bars)
    if len(m60_bars) < 6:
        return False
    decline = [bar for bar in m60_bars[-5:-2] if bar.close < bar.open]
    rebound = [bar for bar in m60_bars[-2:] if bar.close >= bar.open]
    if not decline or not rebound:
        return False
    decline_avg = sum(bar.volume for bar in decline) / len(decline)
    rebound_avg = sum(bar.volume for bar in rebound) / len(rebound)
    return rebound_avg < decline_avg * 0.85
