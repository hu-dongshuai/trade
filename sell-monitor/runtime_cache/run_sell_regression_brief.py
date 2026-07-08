from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path

from sell_monitor.app.backtest import (
    SELL_ALERT_DEDUPE_DAYS,
    _adjust_missed_after_prior_sell_alerts,
    _build_backtest_decision,
    _build_event,
    _dedupe_sell_alerts,
    summarize_events,
)
from sell_monitor.config import load_default_config
from sell_monitor.data.provider_factory import build_market_data_provider
from sell_monitor.domain.enums import Action
from sell_monitor.domain.models import Position
from sell_monitor.storage.position_store import JsonPositionStore
from sell_monitor.storage.user_rule_store import JsonUserRuleStore


ROOT = Path(r"C:\Users\admin\Documents\New project\sell-monitor\runtime_cache")
OUTPUT = ROOT / "sell_regression_brief_20260708.md"
START_DT = datetime(2025, 3, 1)
END_DT = datetime(2026, 6, 30, 15, 0)


def main() -> None:
    config = load_default_config()
    provider = build_market_data_provider(config)
    provider.get_symbol_name = lambda s: s
    positions = JsonPositionStore(config.positions_path).load_all()
    rules = JsonUserRuleStore(config.user_rules_path).load_all()

    try:
        symbols = _load_symbols()
        refresh_notices: list[str] = []
        for sym in symbols:
            try:
                provider.get_daily_bars_until(sym, END_DT, limit=5000)
                provider.get_m15_bars_until(sym, END_DT, limit=7000)
            except Exception as exc:  # pragma: no cover - runtime dependent
                refresh_notices.append(f"[{sym}] refresh failed: {exc}")

        coverage: list[tuple[str, str, str, int]] = []
        all_events = []
        for sym in symbols:
            try:
                daily_bars = provider.get_daily_bars(sym, limit=5000)
                m15_bars = provider.get_m15_bars(sym, limit=7000)
            except Exception as exc:  # pragma: no cover - runtime dependent
                refresh_notices.append(f"[{sym}] load failed: {exc}")
                continue

            if not daily_bars or not m15_bars:
                continue

            use_start = max(START_DT.date(), m15_bars[0].ts.date())
            use_end = min(END_DT.date(), daily_bars[-1].ts.date(), m15_bars[-1].ts.date())
            if use_start > use_end:
                continue

            coverage.append((sym, use_start.isoformat(), use_end.isoformat(), len(m15_bars)))
            position = positions.get(sym) or Position(symbol=sym, cost_price=daily_bars[0].close, quantity=1)
            symbol_name = getattr(provider, "get_symbol_name", lambda s: s)(sym)
            test_days = [bar for bar in daily_bars if use_start <= bar.ts.date() <= use_end]

            symbol_events = []
            for day_bar in test_days:
                as_of_dt = datetime.combine(day_bar.ts.date(), time(15, 0))
                daily_until = [bar for bar in daily_bars if bar.ts <= as_of_dt][-200:]
                m15_until = [bar for bar in m15_bars if bar.ts <= as_of_dt][-200:]
                if not daily_until or not m15_until:
                    continue
                decision = _build_backtest_decision(
                    provider,
                    sym,
                    daily_until,
                    m15_until,
                    position,
                    rules.get(sym),
                    as_of_dt,
                )
                future_daily = [bar for bar in daily_bars if bar.ts.date() > day_bar.ts.date()]
                symbol_events.append(_build_event(sym, symbol_name, day_bar, decision, future_daily))

            symbol_events = _dedupe_sell_alerts(symbol_events, window_days=SELL_ALERT_DEDUPE_DAYS)
            all_events.extend(_adjust_missed_after_prior_sell_alerts(symbol_events))

        summary = summarize_events(all_events)
        by_symbol: dict[str, list] = defaultdict(list)
        for event in all_events:
            by_symbol[event.symbol].append(event)

        lines: list[str] = []
        lines.append("# 卖出监控回归简报")
        lines.append("")
        lines.append(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 回测窗口: {START_DT.strftime('%Y-%m-%d')} 到 {END_DT.strftime('%Y-%m-%d')}")
        lines.append(f"- 样本股票数: {len(coverage)}")
        lines.append(f"- 总事件数: {len(all_events)}")
        lines.append("")
        lines.append("## 核心结果")
        lines.append("")
        lines.append(f"- 减仓提醒: {summary['reduce_total']} 次，命中 {summary['reduce_hit']}，误报 {summary['reduce_false']}")
        lines.append(f"- 清仓/止损提醒: {summary['exit_total']} 次，命中 {summary['exit_hit']}，误报 {summary['exit_false']}")
        lines.append(f"- 漏报: {summary['missed']}")
        reduce_rate = (summary["reduce_hit"] / summary["reduce_total"] * 100) if summary["reduce_total"] else 0.0
        exit_rate = (summary["exit_hit"] / summary["exit_total"] * 100) if summary["exit_total"] else 0.0
        reduce_false_rate = (summary["reduce_false"] / summary["reduce_total"] * 100) if summary["reduce_total"] else 0.0
        exit_false_rate = (summary["exit_false"] / summary["exit_total"] * 100) if summary["exit_total"] else 0.0
        lines.append(f"- 减仓命中率: {reduce_rate:.2f}%")
        lines.append(f"- 清仓/止损命中率: {exit_rate:.2f}%")
        lines.append(f"- 减仓误报率: {reduce_false_rate:.2f}%")
        lines.append(f"- 清仓/止损误报率: {exit_false_rate:.2f}%")
        lines.append("")
        lines.append("## 规则摘要")
        lines.append("")
        lines.append("- 减仓命中: 15个交易日内最大回撤 >= 5%。")
        lines.append("- 清仓/止损命中: 15个交易日内最大回撤 >= 7%。")
        lines.append("- 误报: 未达到对应回撤阈值，但15个交易日内最大上涨 >= 7%。")
        lines.append("- 漏报: HOLD 后15个交易日内最大回撤 >= 7%，且前15个交易日内没有出现卖出提醒。")
        lines.append(f"- 去重: 同一股票 {SELL_ALERT_DEDUPE_DAYS} 个交易日窗口内，只保留最高等级卖出事件。")
        lines.append("- 评分: 背景类信号最多计 1 分，不能单独推动减仓/清仓。")
        lines.append("")
        lines.append("## 覆盖股票")
        lines.append("")
        for sym, start_text, end_text, count in coverage:
            lines.append(f"- {sym}: {start_text} 到 {end_text}，15分钟缓存 {count} 根")
        lines.append("")
        lines.append("## 分股票摘要")
        lines.append("")
        for sym in sorted(by_symbol):
            events = by_symbol[sym]
            reduce_total = sum(1 for event in events if event.action == Action.REDUCE)
            reduce_hit = sum(1 for event in events if event.action == Action.REDUCE and event.outcome == "命中")
            exit_total = sum(1 for event in events if event.action in {Action.EXIT_ALL, Action.STOP_LOSS})
            exit_hit = sum(
                1 for event in events if event.action in {Action.EXIT_ALL, Action.STOP_LOSS} and event.outcome == "命中"
            )
            missed = sum(1 for event in events if event.outcome == "漏报")
            lines.append(f"- {sym}: 减仓 {reduce_hit}/{reduce_total}，清仓/止损 {exit_hit}/{exit_total}，漏报 {missed}")
        if refresh_notices:
            lines.append("")
            lines.append("## 数据提示")
            lines.append("")
            for notice in refresh_notices[:20]:
                lines.append(f"- {notice}")

        OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(OUTPUT)
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()


def _load_symbols() -> list[str]:
    symbols: list[str] = []
    for path in sorted(ROOT.glob("*_15m.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        bars = payload.get("bars", [])
        if bars:
            symbols.append(path.stem.replace("_15m", ""))
    return symbols


if __name__ == "__main__":
    main()
