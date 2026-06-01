from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Bar, Decision, Position, PriceZone, UserRule
from sell_monitor.monitor.daily_context_builder import build_daily_context_from_data
from sell_monitor.monitor.intraday_monitor import run_intraday_monitor
from sell_monitor.scoring.decision_engine import build_decision
from sell_monitor.scoring.fundamental_weight import apply_fundamental_weight, load_fundamental_assessment
from sell_monitor.scoring.hard_rule_engine import evaluate_hard_rules
from sell_monitor.scoring.score_engine import compute_score
from sell_monitor.scoring.support_protection import (
    apply_a_level_support_bias_filter,
    apply_exit_support_protection,
    apply_support_protection,
)


@dataclass(frozen=True)
class ReplayDecisionResult:
    decision: Decision
    notices: list[str]
    zones: list[PriceZone]
    daily_bars: list[Bar]


def build_replay_decision(
    provider,
    symbol: str,
    as_of_dt: datetime,
    position: Position,
    rule: UserRule | None,
) -> ReplayDecisionResult:
    daily_bars, m15_bars, quote_price, _ = _load_replay_market_data(provider, symbol, as_of_dt)
    notices: list[str] = []
    daily_context = build_daily_context_from_data(
        symbol=symbol,
        current_price=quote_price,
        daily_bars=daily_bars,
        market_state="neutral",
        sector_state="neutral",
        cache=None,
        cache_key=None,
        notices=notices,
    )
    if daily_context.active_zone is None:
        decision = Decision(
            symbol=symbol,
            action=Action.HOLD,
            total_score=0,
            priority=Priority.NORMAL,
            reasons=["当时未接近日线 A/B 级关键价位或 C 级压力位"],
            next_step="继续观察，等待价格进入高优先级关键价位或 C 级压力位附近",
            cancel_condition="若后续接近日线 A/B 级关键价位或 C 级压力位，再重新评估15分钟卖出信号",
        )
        return ReplayDecisionResult(
            decision=decision,
            notices=notices,
            zones=daily_context.daily_zones,
            daily_bars=daily_context.daily_bars,
        )

    signals = run_intraday_monitor(daily_context, daily_bars, m15_bars)
    hard = evaluate_hard_rules(
        symbol=symbol,
        current_price=daily_context.current_price,
        position=position,
        rule=rule,
        signals=signals,
    )
    if hard:
        decision = apply_exit_support_protection(hard, daily_context, daily_bars)
        decision = apply_support_protection(decision, daily_context, daily_bars, m15_bars, signals)
        decision = apply_a_level_support_bias_filter(decision, daily_context)
    else:
        decision = build_decision(symbol, compute_score(signals), signals)
        decision = apply_fundamental_weight(decision, load_fundamental_assessment(provider, symbol, as_of_dt))
        decision = apply_support_protection(decision, daily_context, daily_bars, m15_bars, signals)
        decision = apply_a_level_support_bias_filter(decision, daily_context)
    return ReplayDecisionResult(
        decision=decision,
        notices=notices,
        zones=daily_context.daily_zones,
        daily_bars=daily_context.daily_bars,
    )


def _load_replay_market_data(provider, symbol: str, as_of_dt: datetime):
    if hasattr(provider, "get_daily_bars_until") and hasattr(provider, "get_m15_bars_until"):
        daily_bars = provider.get_daily_bars_until(symbol, as_of_dt, limit=200)
        m15_bars = provider.get_m15_bars_until(symbol, as_of_dt, limit=200)
    else:
        daily_bars = [bar for bar in provider.get_daily_bars(symbol, limit=1000) if bar.ts <= as_of_dt][-200:]
        m15_bars = [bar for bar in provider.get_m15_bars(symbol, limit=1000) if bar.ts <= as_of_dt][-200:]

    if not daily_bars:
        raise MarketDataError(f"[{symbol}] 在 {as_of_dt.strftime('%Y-%m-%d %H:%M:%S')} 之前没有可用日线数据")
    if not m15_bars:
        raise MarketDataError(f"[{symbol}] 在 {as_of_dt.strftime('%Y-%m-%d %H:%M:%S')} 之前没有可用15分钟数据")

    quote_bar = m15_bars[-1]
    return daily_bars, m15_bars, quote_bar.close, quote_bar.ts
