from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sell_monitor.config import load_default_config
from sell_monitor.data.provider_factory import build_market_data_provider
from sell_monitor.domain.enums import EntryAction
from sell_monitor.entry.entry_scan_service import EntryScanService
from sell_monitor.notifier.channels.telegram import TelegramChannel
from sell_monitor.notifier.channels.entry_obsidian import ObsidianEntryRunRecorder
from sell_monitor.notifier.entry_dispatcher import EntryAlertDispatcher, EntryConsoleChannel
from sell_monitor.notifier.symbol_display import display_symbol
from sell_monitor.storage.watchlist_factory import build_watchlist_store
from sell_monitor.trading_time import describe_a_share_trading_hours, is_a_share_trading_time, now_china


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the entry-monitor rule engine.")
    parser.add_argument("--base-dir", type=Path, default=None, help="Project base directory.")
    parser.add_argument("--symbol", type=str, default=None, help="Only scan one symbol.")
    parser.add_argument(
        "--ignore-trading-hours",
        action="store_true",
        help="Run once even outside A-share trading hours.",
    )
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args()
    config = load_default_config(args.base_dir)
    print(f"Using provider: {config.provider}")
    current_time = now_china()
    if not args.ignore_trading_hours and not is_a_share_trading_time(current_time):
        print(
            f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] 非A股交易时段，跳过本轮实时开仓检查。"
            f"{describe_a_share_trading_hours()}。"
        )
        return 0

    if not config.obsidian_entry:
        print("未配置 Obsidian 开仓检查目录或 watchlist 路径。")
        return 1

    watchlist_store = build_watchlist_store(config, mode="entry")
    provider = build_market_data_provider(config)
    recorder = ObsidianEntryRunRecorder(config.obsidian_entry)
    dispatcher = EntryAlertDispatcher(channels=[EntryConsoleChannel()])
    telegram_channel = TelegramChannel(config.telegram) if config.telegram else None
    service = EntryScanService(data_provider=provider, watchlist_store=watchlist_store)

    symbols = [args.symbol] if args.symbol else watchlist_store.load()
    symbol_names = watchlist_store.load_name_map()
    try:
        result = service.run(symbol_filter=args.symbol)
    except Exception as exc:
        print(f"运行失败：{exc}")
        close = getattr(provider, "close", None)
        if callable(close):
            close()
        return 1

    all_notices: list[str] = []
    if hasattr(provider, "consume_notices"):
        all_notices.extend(provider.consume_notices())
    all_notices.extend(result.notices)
    for notice in all_notices:
        print(notice)

    recorder.write_run(
        symbols=symbols,
        decisions=result.decisions,
        notices=all_notices,
        symbol_names=symbol_names,
        zone_snapshots=result.zone_snapshots,
        daily_bar_snapshots=result.daily_bar_snapshots,
    )
    for decision in result.decisions:
        dispatcher.dispatch(decision)
        if telegram_channel and _should_send_entry_telegram(decision):
            try:
                telegram_channel.send(
                    subject=f"{config.telegram.subject_prefix} 开仓提醒 {display_symbol(decision.symbol, decision.symbol_name)} score={decision.entry_score}",
                    message=_format_entry_telegram_message(decision),
                )
            except Exception as exc:
                print(f"[Telegram] {display_symbol(decision.symbol, decision.symbol_name)} 发送失败: {exc}")

    close = getattr(provider, "close", None)
    if callable(close):
        close()
    return 0


def _should_send_entry_telegram(decision) -> bool:
    return decision.allowed and decision.action == EntryAction.ALLOW_ENTRY


def _format_entry_telegram_message(decision) -> str:
    reason_lines = "\n".join(f"- {reason}" for reason in decision.reasons[:6]) or "- 无"
    return (
        f"股票: {display_symbol(decision.symbol, decision.symbol_name)}\n"
        f"类型: 买入\n"
        f"动作: {decision.action.value}\n"
        f"分数: {decision.entry_score}\n"
        f"理由:\n{reason_lines}\n"
        f"计划挂单价: {_fmt(decision.planned_entry_price)}\n"
        f"止损价: {_fmt(decision.stop_loss_price)}\n"
        f"第一止盈位: {_fmt(decision.first_take_profit_price)}"
    )


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
