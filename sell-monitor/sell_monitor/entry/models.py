from __future__ import annotations

from dataclasses import dataclass, field

from sell_monitor.domain.models import PriceZone


@dataclass(frozen=True)
class EntryCandidate:
    model: str
    score: int
    planned_entry_price: float | None
    stop_loss_price: float | None
    first_take_profit_price: float | None
    risk_reward_ratio: float | None
    reasons: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    hard_blocking_reasons: list[str] = field(default_factory=list)
    support_zone: PriceZone | None = None
    target_zone: PriceZone | None = None


@dataclass(frozen=True)
class EntryContext:
    symbol: str
    symbol_name: str | None
    current_price: float
    market_state: str
    sector_state: str
    daily_trend: str
    is_trend_healthy: bool
    is_m60_trend_healthy: bool
    daily_relative_strength_ok: bool
    liquidity_ok: bool
    avg_daily_turnover: float
    recent_5d_return: float
    recent_10d_return: float
    weekly_background: str
    accumulation_score: int
    accumulation_reasons: list[str]
    weekly_support_zones: list[PriceZone]
    weekly_resistance_zones: list[PriceZone]
    daily_support_zones: list[PriceZone]
    daily_resistance_zones: list[PriceZone]
