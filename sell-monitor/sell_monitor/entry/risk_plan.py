from __future__ import annotations

from sell_monitor.domain.models import Bar, PriceZone
from sell_monitor.indicators.atr import compute_atr


def plan_pullback_trade(
    current_price: float,
    support_zone: PriceZone,
    target_zone: PriceZone | None,
    m15_bars: list[Bar],
) -> tuple[float | None, float | None, float | None, float | None]:
    if not support_zone:
        return None, None, None, None
    atr15 = compute_atr(m15_bars, 14) if len(m15_bars) >= 15 else 0.0
    buffer_size = atr15 * 2 if atr15 > 0 else max(current_price * 0.01, 0.01)
    planned_entry_price = round((support_zone.low + support_zone.high) / 2, 2)
    stop_loss_price = round(max(0.01, support_zone.low - buffer_size), 2)
    first_take_profit_price = round(target_zone.low, 2) if target_zone else None
    rr = _risk_reward_ratio(planned_entry_price, stop_loss_price, first_take_profit_price)
    return planned_entry_price, stop_loss_price, first_take_profit_price, rr


def plan_breakout_trade(
    breakout_level: float,
    target_zone: PriceZone | None,
    m15_bars: list[Bar],
) -> tuple[float | None, float | None, float | None, float | None]:
    atr15 = compute_atr(m15_bars, 14) if len(m15_bars) >= 15 else 0.0
    buffer_size = atr15 * 2 if atr15 > 0 else max(breakout_level * 0.01, 0.01)
    planned_entry_price = round(breakout_level, 2)
    stop_loss_price = round(max(0.01, breakout_level - buffer_size), 2)
    first_take_profit_price = round(target_zone.low, 2) if target_zone else None
    rr = _risk_reward_ratio(planned_entry_price, stop_loss_price, first_take_profit_price)
    return planned_entry_price, stop_loss_price, first_take_profit_price, rr


def _risk_reward_ratio(
    planned_entry_price: float | None,
    stop_loss_price: float | None,
    first_take_profit_price: float | None,
) -> float | None:
    if (
        planned_entry_price is None
        or stop_loss_price is None
        or first_take_profit_price is None
        or planned_entry_price <= stop_loss_price
        or first_take_profit_price <= planned_entry_price
    ):
        return None
    risk = planned_entry_price - stop_loss_price
    reward = first_take_profit_price - planned_entry_price
    if risk <= 0:
        return None
    return round(reward / risk, 2)
