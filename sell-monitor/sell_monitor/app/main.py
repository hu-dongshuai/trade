from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sell_monitor.config import load_default_config
from sell_monitor.data.provider_factory import build_market_data_provider
from sell_monitor.monitor.sell_monitor_service import SellMonitorService
from sell_monitor.notifier.alert_dispatcher import ConsoleAlertDispatcher, ConsoleChannel
from sell_monitor.notifier.channels.email import EmailChannel
from sell_monitor.notifier.channels.obsidian import ObsidianMonitorRunRecorder
from sell_monitor.storage.position_store import JsonPositionStore
from sell_monitor.storage.user_rule_store import JsonUserRuleStore
from sell_monitor.storage.watchlist_store import JsonWatchlistStore
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
    current_time = now_china()
    if not args.ignore_trading_hours and not is_a_share_trading_time(current_time):
        print(
            f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] 非A股交易时段，跳过本轮实时检测。"
            f"{describe_a_share_trading_hours()}。"
        )
        return 0

    watchlist_store = JsonWatchlistStore(config.watchlist_path)
    position_store = JsonPositionStore(config.positions_path)
    user_rule_store = JsonUserRuleStore(config.user_rules_path)
    provider = build_market_data_provider(config)
    channels = []
    if config.email:
        channels.append(EmailChannel(config.email))
    channels.append(ConsoleChannel())
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
    try:
        result = service.run(symbol_filter=args.symbol)
    except Exception as exc:
        print(f"运行失败：{exc}")
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
        symbols = [args.symbol] if args.symbol else watchlist_store.load()
        obsidian_recorder.write_run(symbols=symbols, decisions=result.decisions, notices=all_notices)
    for decision in result.decisions:
        notifier.dispatch(decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
