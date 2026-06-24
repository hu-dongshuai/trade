from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sell_monitor.domain.models import Bar, EntryDecision, PriceZone
from sell_monitor.entry.context_builder import build_entry_context
from sell_monitor.entry.decision_engine import build_entry_decision
from sell_monitor.entry.model_detector import detect_entry_candidates
from sell_monitor.monitor.daily_context_builder import build_daily_context_from_data
from sell_monitor.monitor.replay_decision import _load_replay_market_data


@dataclass(frozen=True)
class ReplayEntryDecisionResult:
    decision: EntryDecision
    notices: list[str]
    zones: list[PriceZone]
    daily_bars: list[Bar]


def build_replay_entry_decision(provider, symbol: str, as_of_dt: datetime) -> ReplayEntryDecisionResult:
    daily_bars, m15_bars, quote_price, _ = _load_replay_market_data(provider, symbol, as_of_dt)
    symbol_name = getattr(provider, "get_symbol_name", lambda s: s)(symbol)
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
    entry_context = build_entry_context(daily_context, symbol_name=symbol_name)
    decision = build_entry_decision(entry_context, detect_entry_candidates(entry_context, daily_bars, m15_bars))
    return ReplayEntryDecisionResult(
        decision=decision,
        notices=notices,
        zones=daily_context.daily_zones,
        daily_bars=daily_context.daily_bars,
    )
