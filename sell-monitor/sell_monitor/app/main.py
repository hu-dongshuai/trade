from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sell_monitor.config import load_default_config
from sell_monitor.data.provider_factory import build_market_data_provider
from sell_monitor.monitor.obsidian_backfill import backfill_missing_obsidian_records
from sell_monitor.monitor.sell_monitor_service import SellMonitorService
from sell_monitor.notifier.alert_dispatcher import ConsoleAlertDispatcher, ConsoleChannel
from sell_monitor.notifier.channels.email import EmailChannel
from sell_monitor.notifier.channels.obsidian import ObsidianMonitorRunRecorder
from sell_monitor.notifier.channels.telegram import TelegramChannel
from sell_monitor.notifier.symbol_display import display_symbol
from sell_monitor.storage.position_store import JsonPositionStore
from sell_monitor.storage.user_rule_store import JsonUserRuleStore
from sell_monitor.storage.watchlist_factory import build_watchlist_store
from sell_monitor.domain.enums import Action
from sell_monitor.trading_time import describe_a_share_trading_hours, is_a_share_trading_time, now_china


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the sell-monitor rule engine.")
    parser.add_argument("--base-dir", type=Path, default=None, help="Project base directory.")
    parser.add_argument("--symbol", type=str, default=None, help="Only monitor one symbol.")
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
            f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] 非A股交易时段，跳过本轮实时检测。"
            f"{describe_a_share_trading_hours()}。"
        )
        return 0

    watchlist_store = build_watchlist_store(config, mode="sell")
    position_store = JsonPositionStore(config.positions_path)
    user_rule_store = JsonUserRuleStore(config.user_rules_path)
    provider = build_market_data_provider(config)
    channels = []
    if config.email:
        channels.append(EmailChannel(config.email))
    channels.append(ConsoleChannel())
    telegram_channel = TelegramChannel(config.telegram) if config.telegram else None
    obsidian_recorder = ObsidianMonitorRunRecorder(config.obsidian_monitor) if config.obsidian_monitor else None
    notifier = ConsoleAlertDispatcher(
        channels=channels,
        subject_prefix=config.email.subject_prefix if config.email else "[SellMonitor]",
    )

    service = SellMonitorService(
        data_provider=provider,
        watchlist_store=watchlist_store,
        position_store=position_store,
        user_rule_store=user_rule_store,
        notifier=notifier,
    )
    symbols = [args.symbol] if args.symbol else watchlist_store.load()
    watchlist_name_map = watchlist_store.load_name_map()
    symbol_names = {
        symbol: watchlist_name_map.get(symbol) or getattr(provider, "get_symbol_name", lambda s: s)(symbol)
        for symbol in symbols
    }
    if obsidian_recorder:
        backfill_notices = backfill_missing_obsidian_records(
            provider=provider,
            recorder=obsidian_recorder,
            symbols=symbols,
            symbol_names=symbol_names,
            positions=position_store.load_all(),
            rules=user_rule_store.load_all(),
            current_time=current_time,
        )
        for notice in backfill_notices:
            print(notice)
    try:
        result = service.run(symbol_filter=args.symbol)
    except Exception as exc:
        print(f"运行失败：{exc}")
        close = getattr(provider, "close", None)
        if callable(close):
            close()
        return 1
    all_notices = []
    if hasattr(provider, "consume_notices"):
        all_notices.extend(provider.consume_notices())
        for notice in all_notices:
            print(notice)
    for notice in result.notices:
        all_notices.append(notice)
        print(notice)
    if obsidian_recorder:
        obsidian_recorder.write_run(
            symbols=symbols,
            decisions=result.decisions,
            notices=all_notices,
            symbol_names=symbol_names,
            zone_snapshots=result.zone_snapshots,
            daily_bar_snapshots=result.daily_bar_snapshots,
        )
    for decision in result.decisions:
        notifier.dispatch(decision)
        if telegram_channel and _should_send_sell_telegram(decision):
            try:
                telegram_channel.send(
                    subject=f"{config.telegram.subject_prefix} 卖出提醒 {display_symbol(decision.symbol, decision.symbol_name)} score={decision.total_score}",
                    message=_format_sell_telegram_message(decision),
                )
            except Exception as exc:
                print(f"[Telegram] {display_symbol(decision.symbol, decision.symbol_name)} 发送失败: {exc}")
    close = getattr(provider, "close", None)
    if callable(close):
        close()
    return 0


def _should_send_sell_telegram(decision) -> bool:
    return decision.action in {Action.REDUCE, Action.STOP_LOSS, Action.EXIT_ALL} and decision.total_score >= 8


def _format_sell_telegram_message(decision) -> str:
    reason_lines = "\n".join(f"- {reason}" for reason in decision.reasons[:6]) or "- 无"
    return (
        f"股票: {display_symbol(decision.symbol, decision.symbol_name)}\n"
        f"类型: 卖出\n"
        f"动作: {decision.action.value}\n"
        f"分数: {decision.total_score}\n"
        f"理由:\n{reason_lines}\n"
        f"下一步: {decision.next_step}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
