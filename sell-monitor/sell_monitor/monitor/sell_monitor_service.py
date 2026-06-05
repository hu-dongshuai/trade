from __future__ import annotations

from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.market_data_provider import MarketDataProvider
from sell_monitor.domain.models import Decision, MonitorRunResult, Position
from sell_monitor.monitor.daily_context_builder import build_daily_context
from sell_monitor.monitor.intraday_monitor import run_intraday_monitor
from sell_monitor.scoring.decision_engine import build_decision
from sell_monitor.scoring.hard_rule_engine import evaluate_hard_rules
from sell_monitor.scoring.hold_protection import apply_hold_protection_reference
from sell_monitor.scoring.score_engine import compute_score
from sell_monitor.storage.position_store import JsonPositionStore
from sell_monitor.storage.user_rule_store import JsonUserRuleStore
from sell_monitor.storage.watchlist_store import JsonWatchlistStore


class SellMonitorService:
    def __init__(
        self,
        data_provider: MarketDataProvider,
        watchlist_store: JsonWatchlistStore,
        position_store: JsonPositionStore,
        user_rule_store: JsonUserRuleStore,
        notifier,
    ) -> None:
        self.data_provider = data_provider
        self.watchlist_store = watchlist_store
        self.position_store = position_store
        self.user_rule_store = user_rule_store
        self.notifier = notifier

    def run(self, symbol_filter: str | None = None) -> MonitorRunResult:
        symbols = self.watchlist_store.load()
        rules = self.user_rule_store.load_all()

        decisions: list[Decision] = []
        notices: list[str] = []
        zone_snapshots = {}
        daily_bar_snapshots = {}
        if symbol_filter:
            if symbol_filter not in symbols:
                self.watchlist_store.ensure_symbol(symbol_filter)
                symbols.append(symbol_filter)
                notices.append(f"[{symbol_filter}] 不在 watchlist.json 中，已自动加入")
            symbols = [symbol for symbol in symbols if symbol == symbol_filter]
        for symbol in symbols:
            symbol_name = getattr(self.data_provider, "get_symbol_name", lambda s: s)(symbol)
            try:
                daily_context = build_daily_context(self.data_provider, symbol)
            except MarketDataError as exc:
                notices.append(str(exc))
                continue
            zone_snapshots[symbol] = daily_context.daily_zones
            daily_bar_snapshots[symbol] = daily_context.daily_bars
            if daily_context.active_zone is None:
                notices.append(f"[{symbol}] 未接近日线 A/B 级关键价位或 C 级压力位，暂不启动 15 分钟监测")
                continue
            try:
                daily_bars = self.data_provider.get_daily_bars(symbol, limit=200)
                m15_bars = self.data_provider.get_m15_bars(symbol, limit=200)
            except MarketDataError as exc:
                notices.append(str(exc))
                continue
            signals = run_intraday_monitor(daily_context, daily_bars, m15_bars)
            position = Position(symbol=symbol, cost_price=daily_context.current_price, quantity=1)
            hard = evaluate_hard_rules(
                symbol=symbol,
                current_price=daily_context.current_price,
                position=position,
                rule=rules.get(symbol),
                signals=signals,
                symbol_name=symbol_name,
            )
            if hard:
                decisions.append(apply_hold_protection_reference(hard, daily_context, daily_bars, m15_bars))
                continue
            score = compute_score(signals)
            decision = build_decision(
                symbol,
                score,
                signals,
                symbol_name=symbol_name,
                current_price=daily_context.current_price,
            )
            decisions.append(apply_hold_protection_reference(decision, daily_context, daily_bars, m15_bars))
        return MonitorRunResult(
            decisions=decisions,
            notices=notices,
            zone_snapshots=zone_snapshots,
            daily_bar_snapshots=daily_bar_snapshots,
        )
