from __future__ import annotations

from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.domain.models import EntryDecision, EntryScanRunResult
from sell_monitor.entry.context_builder import build_entry_context
from sell_monitor.entry.decision_engine import build_entry_decision
from sell_monitor.entry.model_detector import detect_entry_candidates
from sell_monitor.monitor.daily_context_builder import build_daily_context
from sell_monitor.storage.watchlist_store import JsonWatchlistStore


class EntryScanService:
    def __init__(self, data_provider, watchlist_store: JsonWatchlistStore) -> None:
        self.data_provider = data_provider
        self.watchlist_store = watchlist_store

    def run(self, symbol_filter: str | None = None) -> EntryScanRunResult:
        symbols = self.watchlist_store.load()
        symbol_name_map = self.watchlist_store.load_name_map()
        notices: list[str] = []
        decisions: list[EntryDecision] = []
        zone_snapshots = {}
        daily_bar_snapshots = {}

        if symbol_filter:
            if symbol_filter not in symbols:
                self.watchlist_store.ensure_symbol(symbol_filter)
                symbols.append(symbol_filter)
                notices.append(f"[{symbol_filter}] 不在 watchlist 中，已自动加入。")
            symbols = [symbol for symbol in symbols if symbol == symbol_filter]

        for symbol in symbols:
            symbol_name = symbol_name_map.get(symbol) or getattr(self.data_provider, "get_symbol_name", lambda s: s)(symbol)
            try:
                daily_context = build_daily_context(self.data_provider, symbol)
                daily_bars = self.data_provider.get_daily_bars(symbol, limit=200)
                m15_bars = self.data_provider.get_m15_bars(symbol, limit=200)
            except MarketDataError as exc:
                notices.append(str(exc))
                continue

            zone_snapshots[symbol] = daily_context.daily_zones
            daily_bar_snapshots[symbol] = daily_context.daily_bars
            entry_context = build_entry_context(daily_context, symbol_name=symbol_name)
            candidates = detect_entry_candidates(entry_context, daily_bars, m15_bars)
            decisions.append(build_entry_decision(entry_context, candidates))

        decisions.sort(key=lambda item: (item.allowed, item.entry_score, item.risk_reward_ratio or 0), reverse=True)
        return EntryScanRunResult(
            decisions=decisions,
            notices=notices,
            zone_snapshots=zone_snapshots,
            daily_bar_snapshots=daily_bar_snapshots,
        )
