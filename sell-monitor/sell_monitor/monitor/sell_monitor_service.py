from __future__ import annotations

from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.market_data_provider import MarketDataProvider
from sell_monitor.domain.models import Decision, MonitorRunResult, Position
from sell_monitor.monitor.daily_context_builder import build_daily_context
from sell_monitor.monitor.intraday_monitor import run_intraday_monitor
from sell_monitor.scoring.decision_engine import build_decision
from sell_monitor.scoring.hard_rule_engine import evaluate_hard_rules
from sell_monitor.scoring.score_engine import compute_score
from sell_monitor.scoring.support_protection import (
    apply_a_level_support_bias_filter,
    apply_exit_support_protection,
    apply_support_protection,
)
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
        positions = self.position_store.load_all()
        rules = self.user_rule_store.load_all()

        decisions: list[Decision] = []
        notices: list[str] = []
        if symbol_filter:
            if symbol_filter not in symbols:
                self.watchlist_store.ensure_symbol(symbol_filter)
                symbols.append(symbol_filter)
                notices.append(f"[{symbol_filter}] 不在 watchlist.json 中，已自动加入")
            if symbol_filter not in positions:
                try:
                    quote = self.data_provider.get_latest_quote(symbol_filter)
                    position = Position(symbol=symbol_filter, cost_price=quote.price, quantity=1)
                    created = self.position_store.upsert(position)
                    positions[symbol_filter] = position
                    if created:
                        notices.append(
                            f"[{symbol_filter}] 未持仓，已按当前价 {quote.price:.2f} 自动加入持仓（数量=1）"
                        )
                except MarketDataError as exc:
                    notices.append(str(exc))
                    return MonitorRunResult(decisions=decisions, notices=notices)
            symbols = [symbol for symbol in symbols if symbol == symbol_filter]
        for symbol in symbols:
            position = positions.get(symbol)
            if not position:
                notices.append(f"[{symbol}] 未持仓，已跳过")
                continue
            try:
                daily_context = build_daily_context(self.data_provider, symbol)
            except MarketDataError as exc:
                notices.append(str(exc))
                continue
            if daily_context.active_zone is None:
                notices.append(f"[{symbol}] 未接近日线 A/B 级关键价位，暂不启动 15 分钟监测")
                continue
            try:
                daily_bars = self.data_provider.get_daily_bars(symbol, limit=200)
                m15_bars = self.data_provider.get_m15_bars(symbol, limit=200)
            except MarketDataError as exc:
                notices.append(str(exc))
                continue
            signals = run_intraday_monitor(daily_context, daily_bars, m15_bars)
            hard = evaluate_hard_rules(
                symbol=symbol,
                current_price=daily_context.current_price,
                position=position,
                rule=rules.get(symbol),
                signals=signals,
            )
            if hard:
                hard = apply_exit_support_protection(hard, daily_context, daily_bars)
                hard = apply_support_protection(hard, daily_context, daily_bars, m15_bars, signals)
                hard = apply_a_level_support_bias_filter(hard, daily_context)
                decisions.append(hard)
                continue
            score = compute_score(signals)
            decision = build_decision(symbol, score, signals)
            decision = apply_support_protection(decision, daily_context, daily_bars, m15_bars, signals)
            decisions.append(apply_a_level_support_bias_filter(decision, daily_context))
        return MonitorRunResult(decisions=decisions, notices=notices)
