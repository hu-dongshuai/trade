from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

from sell_monitor.config import load_default_config
from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.provider_factory import build_market_data_provider
from sell_monitor.domain.models import Bar, EntryDecision, PriceZone
from sell_monitor.entry.replay_entry_decision import build_replay_entry_decision
from sell_monitor.notifier.zone_table_formatter import format_multi_symbol_zone_tables
from sell_monitor.storage.watchlist_factory import build_watchlist_store


@dataclass(frozen=True)
class EntryBacktestEvent:
    symbol: str
    symbol_name: str | None
    as_of_date: str
    allowed: bool
    entry_model: str
    entry_score: int
    planned_entry_price: float | None
    stop_loss_price: float | None
    first_take_profit_price: float | None
    risk_reward_ratio: float | None
    hit_tp1: bool
    hit_stop: bool
    max_runup_15d: float
    max_drawdown_15d: float
    reason: str


@dataclass(frozen=True)
class EntryBacktestResult:
    events: list[EntryBacktestEvent]
    notices: list[str]
    zone_snapshots: dict[str, list[PriceZone]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch backtest entry-monitor advice.")
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
    symbols = _parse_symbols(args.symbols) or build_watchlist_store(config, mode="entry").load()

    try:
        result = run_backtest(provider, symbols, start_dt, end_dt)
        output_path = args.output or _default_report_path(config, args.start_date, args.end_date, symbols)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(format_backtest_report(result, args.start_date, args.end_date), encoding="utf-8")
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()

    for notice in result.notices:
        print(notice)
    print(f"Entry backtest report written to {output_path}")
    return 0


def run_backtest(provider, symbols: list[str], start_dt: datetime, end_dt: datetime) -> EntryBacktestResult:
    events: list[EntryBacktestEvent] = []
    notices: list[str] = []
    zone_snapshots: dict[str, list[PriceZone]] = {}
    for symbol in symbols:
        symbol_name = getattr(provider, "get_symbol_name", lambda s: s)(symbol)
        try:
            daily_bars = provider.get_daily_bars(symbol, limit=5000)
        except MarketDataError as exc:
            notices.append(str(exc))
            continue
        if not daily_bars:
            notices.append(f"[{symbol}] 没有可用日线数据，跳过。")
            continue

        test_days = [bar for bar in daily_bars if start_dt.date() <= bar.ts.date() <= end_dt.date()]
        for day_bar in test_days:
            as_of_dt = datetime.combine(day_bar.ts.date(), time(15, 0, 0))
            try:
                replay = build_replay_entry_decision(provider, symbol, as_of_dt)
            except MarketDataError as exc:
                notices.append(str(exc))
                break
            zone_snapshots[symbol] = replay.zones
            future_daily = [bar for bar in daily_bars if bar.ts.date() > day_bar.ts.date()][:15]
            events.append(_build_event(symbol, symbol_name, day_bar, replay.decision, future_daily))
    return EntryBacktestResult(events=events, notices=notices, zone_snapshots=zone_snapshots)


def format_backtest_report(result: EntryBacktestResult, start_date: str, end_date: str) -> str:
    allowed = [event for event in result.events if event.allowed]
    tp1_hits = sum(1 for event in allowed if event.hit_tp1)
    stop_hits = sum(1 for event in allowed if event.hit_stop)
    lines = [
        f"# 开仓检测回测 {start_date} 至 {end_date}",
        "",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 回测事件数: {len(result.events)}",
        f"- 允许开仓次数: {len(allowed)}",
        f"- 第一止盈位触达次数: {tp1_hits}",
        f"- 止损触发次数: {stop_hits}",
        "",
    ]
    lines.extend(format_multi_symbol_zone_tables(result.zone_snapshots))
    if result.notices:
        lines.extend(["## 数据提示", ""])
        lines.extend(f"- {notice}" for notice in result.notices)
        lines.append("")
    lines.extend(
        [
            "## 明细",
            "",
            "| 日期 | 股票代码 | 股票名称 | 允许开仓 | 开仓模型 | 开仓分数 | 计划挂单价 | 止损价 | 第一止盈位 | 盈亏比 | 15日最大上涨 | 15日最大回撤 | TP1触达 | 止损触发 | 原因 |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for event in result.events:
        lines.append(
            f"| {event.as_of_date} | {event.symbol} | {event.symbol_name or event.symbol} | {'是' if event.allowed else '否'} | {event.entry_model} | {event.entry_score} | "
            f"{_fmt(event.planned_entry_price)} | {_fmt(event.stop_loss_price)} | {_fmt(event.first_take_profit_price)} | {_fmt(event.risk_reward_ratio)} | "
            f"{event.max_runup_15d:.2f}% | {event.max_drawdown_15d:.2f}% | {'是' if event.hit_tp1 else '否'} | {'是' if event.hit_stop else '否'} | {event.reason} |"
        )
    return "\n".join(lines) + "\n"


def _build_event(
    symbol: str,
    symbol_name: str | None,
    day_bar: Bar,
    decision: EntryDecision,
    future_daily: list[Bar],
) -> EntryBacktestEvent:
    planned_entry_price = decision.planned_entry_price or day_bar.close
    max_runup = _max_runup_pct(planned_entry_price, future_daily)
    max_drawdown = _max_drawdown_pct(planned_entry_price, future_daily)
    hit_tp1 = _hit_target(decision.first_take_profit_price, future_daily)
    hit_stop = _hit_stop(decision.stop_loss_price, future_daily)
    reason = "；".join(decision.reasons + decision.blocking_reasons)
    return EntryBacktestEvent(
        symbol=symbol,
        symbol_name=symbol_name,
        as_of_date=day_bar.ts.strftime("%Y-%m-%d"),
        allowed=decision.allowed,
        entry_model=decision.entry_model,
        entry_score=decision.entry_score,
        planned_entry_price=decision.planned_entry_price,
        stop_loss_price=decision.stop_loss_price,
        first_take_profit_price=decision.first_take_profit_price,
        risk_reward_ratio=decision.risk_reward_ratio,
        hit_tp1=hit_tp1,
        hit_stop=hit_stop,
        max_runup_15d=max_runup,
        max_drawdown_15d=max_drawdown,
        reason=reason,
    )


def _max_runup_pct(price: float, future_daily: list[Bar]) -> float:
    if price <= 0 or not future_daily:
        return 0.0
    return max(0.0, (max(bar.high for bar in future_daily) - price) / price * 100)


def _max_drawdown_pct(price: float, future_daily: list[Bar]) -> float:
    if price <= 0 or not future_daily:
        return 0.0
    return max(0.0, (price - min(bar.low for bar in future_daily)) / price * 100)


def _hit_target(target: float | None, future_daily: list[Bar]) -> bool:
    return target is not None and any(bar.high >= target for bar in future_daily)


def _hit_stop(stop: float | None, future_daily: list[Bar]) -> bool:
    return stop is not None and any(bar.low <= stop for bar in future_daily)


def _parse_symbols(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _default_report_path(config, start_date: str, end_date: str, symbols: list[str]) -> Path:
    if config.obsidian_entry:
        output_dir = config.obsidian_entry.monitor_dir / "backtest"
    else:
        output_dir = config.cache_dir / "entry_backtests"
    symbol_key = "watchlist" if len(symbols) != 1 else symbols[0]
    return output_dir / f"entry_backtest_{symbol_key}_{start_date.replace('-', '')}_{end_date.replace('-', '')}.md"


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
