from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

from sell_monitor.config import load_default_config
from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.provider_factory import build_market_data_provider
from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Bar, Decision, Position, PriceZone, UserRule
from sell_monitor.monitor.daily_context_builder import build_daily_context_from_data
from sell_monitor.monitor.intraday_monitor import run_intraday_monitor
from sell_monitor.monitor.sell_warning_state import with_sell_warning_state
from sell_monitor.notifier.zone_table_formatter import format_multi_symbol_zone_tables
from sell_monitor.scoring.decision_engine import build_decision
from sell_monitor.scoring.hard_rule_engine import evaluate_hard_rules
from sell_monitor.scoring.hold_protection import apply_hold_protection_reference
from sell_monitor.scoring.score_engine import compute_score
from sell_monitor.scoring.warning_mode import cap_warning_state_action
from sell_monitor.storage.position_store import JsonPositionStore
from sell_monitor.storage.user_rule_store import JsonUserRuleStore
from sell_monitor.storage.watchlist_factory import build_watchlist_store


REDUCE_HIT_DRAWDOWN_PCT = 5.0
EXIT_HIT_DRAWDOWN_PCT = 7.0
FALSE_POSITIVE_RUNUP_PCT = 7.0
MISSED_DRAWDOWN_PCT = 7.0
SELL_ALERT_DEDUPE_DAYS = 5

OUTCOME_HIT = "命中"
OUTCOME_FALSE_POSITIVE = "误报"
OUTCOME_MISSED = "漏报"
OUTCOME_COVERED = "已被前序卖点覆盖"
OUTCOME_UNDETERMINED = "待定"
OUTCOME_NO_TRIGGER = "未触发"


@dataclass(frozen=True)
class BacktestEvent:
    symbol: str
    symbol_name: str | None
    as_of_date: str
    action: Action
    score: int
    hold_protection_score: int
    price: float
    drawdown_15d: float
    runup_15d: float
    outcome: str
    reason: str


@dataclass(frozen=True)
class BacktestResult:
    events: list[BacktestEvent]
    notices: list[str]
    zone_snapshots: dict[str, list[PriceZone]] | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch backtest sell-monitor advice.")
    parser.add_argument("--base-dir", type=Path, default=None, help="Project base directory.")
    parser.add_argument("--symbols", type=str, default="", help="Comma-separated symbols. Empty means watchlist.")
    parser.add_argument("--start-date", type=str, required=True, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", type=str, required=True, help="End date in YYYY-MM-DD format.")
    parser.add_argument("--output", type=Path, default=None, help="Optional Markdown report path.")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_parser().parse_args()
    config = load_default_config(args.base_dir)
    print(f"Using provider: {config.provider}")
    provider = build_market_data_provider(config)
    start_dt = datetime.strptime(args.start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end_date, "%Y-%m-%d")
    symbols = _parse_symbols(args.symbols) or build_watchlist_store(config, mode="sell").load()
    positions = JsonPositionStore(config.positions_path).load_all()
    rules = JsonUserRuleStore(config.user_rules_path).load_all()

    try:
        result = run_backtest(provider, symbols, positions, rules, start_dt, end_dt)
        output_path = args.output or _default_report_path(config, args.start_date, args.end_date, symbols)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(format_backtest_report(result, args.start_date, args.end_date), encoding="utf-8")
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()

    for notice in result.notices:
        print(notice)
    print(f"Backtest report written to {output_path}")
    return 0


def run_backtest(
    provider,
    symbols: list[str],
    positions: dict[str, Position],
    rules: dict[str, UserRule],
    start_dt: datetime,
    end_dt: datetime,
) -> BacktestResult:
    events: list[BacktestEvent] = []
    notices: list[str] = []
    zone_snapshots: dict[str, list[PriceZone]] = {}
    for symbol in symbols:
        symbol_name = getattr(provider, "get_symbol_name", lambda s: s)(symbol)
        try:
            daily_bars = provider.get_daily_bars(symbol, limit=5000)
            m15_bars = provider.get_m15_bars(symbol, limit=5000)
        except MarketDataError as exc:
            notices.append(str(exc))
            continue

        if not daily_bars:
            notices.append(f"[{symbol}] 没有可用日线数据，已跳过。")
            continue
        if not m15_bars:
            notices.append(f"[{symbol}] 没有可用15分钟数据，已跳过。")
            continue

        earliest_m15 = m15_bars[0].ts
        if earliest_m15.date() > start_dt.date():
            notices.append(
                f"[{symbol}] 15分钟数据最早仅到 {earliest_m15.strftime('%Y-%m-%d %H:%M:%S')}，"
                "早于该时间的回测日期会自动跳过。"
            )

        position = positions.get(symbol) or Position(symbol=symbol, cost_price=daily_bars[0].close, quantity=1)
        snapshot_daily = [bar for bar in daily_bars if bar.ts.date() <= end_dt.date()][-200:]
        if snapshot_daily:
            snapshot_context = build_daily_context_from_data(
                symbol=symbol,
                current_price=snapshot_daily[-1].close,
                daily_bars=snapshot_daily,
                market_state="neutral",
                sector_state="neutral",
                cache=None,
                cache_key=None,
                notices=[],
            )
            zone_snapshots[symbol] = snapshot_context.daily_zones

        test_days = [bar for bar in daily_bars if start_dt.date() <= bar.ts.date() <= end_dt.date()]
        symbol_events: list[BacktestEvent] = []
        for day_bar in test_days:
            as_of_dt = datetime.combine(day_bar.ts.date(), time(15, 0, 0))
            daily_until = [bar for bar in daily_bars if bar.ts <= as_of_dt][-200:]
            m15_until = [bar for bar in m15_bars if bar.ts <= as_of_dt][-200:]
            if not daily_until or not m15_until:
                continue
            decision = _build_backtest_decision(provider, symbol, daily_until, m15_until, position, rules.get(symbol), as_of_dt)
            future_daily = [bar for bar in daily_bars if bar.ts.date() > day_bar.ts.date()]
            symbol_events.append(_build_event(symbol, symbol_name, day_bar, decision, future_daily))

        deduped_events = _dedupe_sell_alerts(symbol_events, window_days=SELL_ALERT_DEDUPE_DAYS)
        events.extend(_adjust_missed_after_prior_sell_alerts(deduped_events))

    return BacktestResult(events=events, notices=notices, zone_snapshots=zone_snapshots)


def format_backtest_report(result: BacktestResult, start_date: str, end_date: str) -> str:
    summary = summarize_events(result.events)
    lines = [
        f"# 卖出提醒策略回测 {start_date} 至 {end_date}",
        "",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 回测事件数: {len(result.events)}",
        f"- 减仓提醒: {summary['reduce_total']}，命中 {summary['reduce_hit']}，误报 {summary['reduce_false']}",
        f"- 清仓/止损提醒: {summary['exit_total']}，命中 {summary['exit_hit']}，误报 {summary['exit_false']}",
        f"- 漏报: {summary['missed']}",
        "",
        "## 回测规则",
        "",
        f"- 减仓命中: 触发后 15 个交易日内最大回撤 >= {REDUCE_HIT_DRAWDOWN_PCT:.0f}%。",
        f"- 清仓命中: 触发后 15 个交易日内最大回撤 >= {EXIT_HIT_DRAWDOWN_PCT:.0f}%。",
        f"- 误报: 未达到对应回撤阈值，且触发后最大上涨 >= {FALSE_POSITIVE_RUNUP_PCT:.0f}%。",
        f"- 漏报: HOLD 后 15 个交易日内最大回撤 >= {MISSED_DRAWDOWN_PCT:.0f}%，且此前 15 个交易日内没有出现减仓/清仓/止损提醒。",
        f"- 去重: 同一只股票在 {SELL_ALERT_DEDUPE_DAYS} 个交易日窗口内，只保留最高等级的卖出提醒；若等级相同，保留更早的一次。",
        "- 评分收紧: 背景类信号最多只贡献 1 分，不能单独推动卖出动作。",
        "",
    ]
    lines.extend(format_multi_symbol_zone_tables(result.zone_snapshots or {}))
    if result.notices:
        lines.extend(["## 数据提示", ""])
        lines.extend(f"- {notice}" for notice in result.notices)
        lines.append("")

    lines.extend(
        [
            "## 明细",
            "",
            "| 日期 | 股票代码 | 股票名称 | 动作 | 分数 | 持有保护分 | 价格 | 15日最大回撤 | 15日最大上涨 | 结果 | 原因 |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for event in result.events:
        lines.append(
            f"| {event.as_of_date} | {event.symbol} | {event.symbol_name or event.symbol} | {event.action.value} | {event.score} | {event.hold_protection_score} | {event.price:.2f} | "
            f"{event.drawdown_15d:.2f}% | {event.runup_15d:.2f}% | {event.outcome} | {event.reason} |"
        )
    return "\n".join(lines) + "\n"


def summarize_events(events: list[BacktestEvent]) -> dict[str, int]:
    reduce_events = [event for event in events if event.action == Action.REDUCE]
    exit_events = [event for event in events if event.action in {Action.EXIT_ALL, Action.STOP_LOSS}]
    return {
        "reduce_total": len(reduce_events),
        "reduce_hit": sum(1 for event in reduce_events if event.outcome == OUTCOME_HIT),
        "reduce_false": sum(1 for event in reduce_events if event.outcome == OUTCOME_FALSE_POSITIVE),
        "exit_total": len(exit_events),
        "exit_hit": sum(1 for event in exit_events if event.outcome == OUTCOME_HIT),
        "exit_false": sum(1 for event in exit_events if event.outcome == OUTCOME_FALSE_POSITIVE),
        "missed": sum(1 for event in events if event.outcome == OUTCOME_MISSED),
    }


def _build_backtest_decision(
    provider,
    symbol: str,
    daily_bars: list[Bar],
    m15_bars: list[Bar],
    position: Position,
    rule: UserRule | None,
    as_of_dt: datetime,
) -> Decision:
    current_price = m15_bars[-1].close
    symbol_name = getattr(provider, "get_symbol_name", lambda s: s)(symbol)
    daily_context = build_daily_context_from_data(
        symbol=symbol,
        current_price=current_price,
        daily_bars=daily_bars,
        market_state="neutral",
        sector_state="neutral",
        cache=None,
        cache_key=None,
        notices=[],
    )
    daily_context = with_sell_warning_state(daily_context, m15_bars)
    if daily_context.active_zone is None and not daily_context.sell_warning_active:
        return Decision(
            symbol=symbol,
            action=Action.HOLD,
            total_score=0,
            priority=Priority.NORMAL,
            reasons=["当日未接近日线 A/B 级关键价位或 C 级压力位，也未进入日线/60分钟转弱预警态"],
            next_step="继续观察",
            cancel_condition="重新接近日线关键价位，或出现两项以上日线/60分钟转弱条件后再评估",
            symbol_name=symbol_name,
            current_price=current_price,
        )
    signals = run_intraday_monitor(daily_context, daily_bars, m15_bars)
    hard = evaluate_hard_rules(symbol, current_price, position, rule, signals, symbol_name=symbol_name)
    decision = hard or cap_warning_state_action(
        build_decision(
            symbol,
            compute_score(signals),
            signals,
            symbol_name=symbol_name,
            current_price=current_price,
        ),
        daily_context,
    )
    return apply_hold_protection_reference(decision, daily_context, daily_bars, m15_bars)


def _build_event(symbol: str, symbol_name: str | None, day_bar: Bar, decision: Decision, future_daily: list[Bar]) -> BacktestEvent:
    price = day_bar.close
    drawdown_15d = _max_drawdown_pct(price, future_daily[:15])
    runup_15d = _max_runup_pct(price, future_daily[:15])
    outcome = _classify_outcome(decision.action, drawdown_15d, runup_15d)
    return BacktestEvent(
        symbol=symbol,
        symbol_name=symbol_name,
        as_of_date=day_bar.ts.strftime("%Y-%m-%d"),
        action=decision.action,
        score=decision.total_score,
        hold_protection_score=decision.hold_protection_score,
        price=price,
        drawdown_15d=drawdown_15d,
        runup_15d=runup_15d,
        outcome=outcome,
        reason="; ".join(decision.reasons),
    )


def _adjust_missed_after_prior_sell_alerts(events: list[BacktestEvent]) -> list[BacktestEvent]:
    adjusted: list[BacktestEvent] = []
    for event in events:
        if event.outcome == OUTCOME_MISSED and _has_prior_sell_alert(adjusted):
            adjusted.append(
                BacktestEvent(
                    symbol=event.symbol,
                    symbol_name=event.symbol_name,
                    as_of_date=event.as_of_date,
                    action=event.action,
                    score=event.score,
                    hold_protection_score=event.hold_protection_score,
                    price=event.price,
                    drawdown_15d=event.drawdown_15d,
                    runup_15d=event.runup_15d,
                    outcome=OUTCOME_COVERED,
                    reason=event.reason + "; 前15个交易日内已出现减仓/清仓/止损提醒，不计为漏报",
                )
            )
            continue
        adjusted.append(event)
    return adjusted


def _dedupe_sell_alerts(events: list[BacktestEvent], window_days: int) -> list[BacktestEvent]:
    deduped: list[BacktestEvent] = []
    for event in events:
        if event.action not in {Action.REDUCE, Action.EXIT_ALL, Action.STOP_LOSS}:
            deduped.append(event)
            continue

        event_dt = datetime.strptime(event.as_of_date, "%Y-%m-%d")
        if deduped and deduped[-1].action in {Action.REDUCE, Action.EXIT_ALL, Action.STOP_LOSS}:
            previous = deduped[-1]
            previous_dt = datetime.strptime(previous.as_of_date, "%Y-%m-%d")
            if (event_dt - previous_dt).days < window_days:
                if _sell_action_rank(event.action) > _sell_action_rank(previous.action):
                    deduped[-1] = event
                continue

        deduped.append(event)
    return deduped


def _sell_action_rank(action: Action) -> int:
    if action == Action.EXIT_ALL:
        return 3
    if action == Action.STOP_LOSS:
        return 2
    if action == Action.REDUCE:
        return 1
    return 0


def _has_prior_sell_alert(events: list[BacktestEvent]) -> bool:
    prior_window = events[-15:]
    return any(event.action in {Action.REDUCE, Action.EXIT_ALL, Action.STOP_LOSS} for event in prior_window)


def _classify_outcome(action: Action, drawdown_15d: float, runup_15d: float) -> str:
    if action == Action.REDUCE:
        if drawdown_15d >= REDUCE_HIT_DRAWDOWN_PCT:
            return OUTCOME_HIT
        if runup_15d >= FALSE_POSITIVE_RUNUP_PCT:
            return OUTCOME_FALSE_POSITIVE
        return OUTCOME_UNDETERMINED
    if action in {Action.EXIT_ALL, Action.STOP_LOSS}:
        if drawdown_15d >= EXIT_HIT_DRAWDOWN_PCT:
            return OUTCOME_HIT
        if runup_15d >= FALSE_POSITIVE_RUNUP_PCT:
            return OUTCOME_FALSE_POSITIVE
        return OUTCOME_UNDETERMINED
    if drawdown_15d >= MISSED_DRAWDOWN_PCT:
        return OUTCOME_MISSED
    return OUTCOME_NO_TRIGGER


def _max_drawdown_pct(price: float, future_daily: list[Bar]) -> float:
    if price <= 0 or not future_daily:
        return 0.0
    return max(0.0, (price - min(bar.low for bar in future_daily)) / price * 100)


def _max_runup_pct(price: float, future_daily: list[Bar]) -> float:
    if price <= 0 or not future_daily:
        return 0.0
    return max(0.0, (max(bar.high for bar in future_daily) - price) / price * 100)


def _parse_symbols(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _default_report_path(config, start_date: str, end_date: str, symbols: list[str]) -> Path:
    if config.obsidian_monitor:
        output_dir = config.obsidian_monitor.monitor_dir / "backtest"
    else:
        output_dir = config.cache_dir / "backtests"
    symbol_key = "watchlist" if len(symbols) != 1 else symbols[0]
    return output_dir / f"backtest_{symbol_key}_{start_date.replace('-', '')}_{end_date.replace('-', '')}.md"


if __name__ == "__main__":
    raise SystemExit(main())
