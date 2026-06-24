from __future__ import annotations

import argparse
import sys
from datetime import datetime, time
from pathlib import Path

from sell_monitor.config import load_default_config
from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.cache_service import FileMarketDataCache
from sell_monitor.data.provider_factory import build_market_data_provider
from sell_monitor.entry.replay_entry_decision import build_replay_entry_decision
from sell_monitor.notifier.entry_formatter import format_entry_decision
from sell_monitor.notifier.symbol_display import display_symbol


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay entry advice using data up to a historical date.")
    parser.add_argument("--base-dir", type=Path, default=None, help="Project base directory.")
    parser.add_argument("--symbol", type=str, required=True, help="Stock symbol, for example 002241.")
    parser.add_argument("--as-of-date", type=str, required=True, help="Replay date in YYYY-MM-DD format.")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_parser().parse_args()
    as_of_date = datetime.strptime(args.as_of_date, "%Y-%m-%d")
    as_of_dt = datetime.combine(as_of_date.date(), time(15, 0, 0))

    config = load_default_config(args.base_dir)
    provider = build_market_data_provider(config)
    cache = FileMarketDataCache(config.cache_dir)
    symbol_name = getattr(provider, "get_symbol_name", lambda s: s)(args.symbol)

    try:
        result = build_replay_entry_decision(provider, args.symbol, as_of_dt)
    except MarketDataError as exc:
        print(str(exc))
        return 1

    export_path = cache.export_replay_daily_zone_markdown(
        symbol=args.symbol,
        snapshot_key=f"entry_{as_of_date.strftime('%Y%m%d')}",
        latest_daily_ts=result.daily_bars[-1].ts,
        zones=result.zones,
        daily_trend="up",
    )
    result.notices.append(f"[{args.symbol}] 历史关键价位已导出到 {export_path}")

    print(f"Replay entry as of {args.as_of_date} 15:00:00")
    print(f"symbol: {display_symbol(args.symbol, symbol_name)}")
    for notice in result.notices:
        print(notice)
    print(format_entry_decision(result.decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
