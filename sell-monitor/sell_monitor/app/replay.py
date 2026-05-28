from __future__ import annotations

import argparse
import sys
from datetime import datetime, time
from pathlib import Path

from sell_monitor.config import load_default_config
from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.cache_service import FileMarketDataCache
from sell_monitor.data.provider_factory import build_market_data_provider
from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Decision, Position
from sell_monitor.monitor.daily_context_builder import build_daily_context_from_data
from sell_monitor.monitor.intraday_monitor import run_intraday_monitor
from sell_monitor.notifier.alert_formatter import format_decision
from sell_monitor.scoring.decision_engine import build_decision
from sell_monitor.scoring.hard_rule_engine import evaluate_hard_rules
from sell_monitor.scoring.score_engine import compute_score
from sell_monitor.scoring.support_protection import apply_support_protection
from sell_monitor.storage.position_store import JsonPositionStore
from sell_monitor.storage.user_rule_store import JsonUserRuleStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay sell-monitor advice using data up to a historical date.")
    parser.add_argument("--base-dir", type=Path, default=None, help="Project base directory.")
    parser.add_argument("--symbol", type=str, required=True, help="Stock symbol, for example 002241.")
    parser.add_argument("--as-of-date", type=str, required=True, help="Replay date in YYYY-MM-DD format.")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args()
    as_of_date = datetime.strptime(args.as_of_date, "%Y-%m-%d")
    as_of_dt = datetime.combine(as_of_date.date(), time(15, 0, 0))

    config = load_default_config(args.base_dir)
    provider = build_market_data_provider(config)
    cache = FileMarketDataCache(config.cache_dir)

    try:
        daily_bars, m15_bars, quote_price, quote_ts = _load_replay_market_data(provider, args.symbol, as_of_dt)
    except MarketDataError as exc:
        print(str(exc))
        return 1

    if not daily_bars:
        print(f"[{args.symbol}] 在 {args.as_of_date} 之前没有可用日线数据")
        return 1
    if not m15_bars:
        print(f"[{args.symbol}] 在 {args.as_of_date} 之前没有可用15分钟数据")
        return 1

    notices: list[str] = []
    if hasattr(provider, "consume_notices"):
        notices.extend(provider.consume_notices())

    daily_context = build_daily_context_from_data(
        symbol=args.symbol,
        current_price=quote_price,
        daily_bars=daily_bars,
        market_state="neutral",
        sector_state="neutral",
        cache=None,
        cache_key=None,
        notices=notices,
    )
    export_path = cache.export_replay_daily_zone_markdown(
        symbol=args.symbol,
        snapshot_key=as_of_date.strftime("%Y%m%d"),
        latest_daily_ts=daily_bars[-1].ts,
        zones=daily_context.daily_zones,
        daily_trend=daily_context.daily_trend,
    )
    notices.append(f"[{args.symbol}] 历史关键价位已导出到 {export_path}")

    positions = JsonPositionStore(config.positions_path).load_all()
    rules = JsonUserRuleStore(config.user_rules_path).load_all()
    position = positions.get(args.symbol) or Position(symbol=args.symbol, cost_price=quote_price, quantity=1)

    if daily_context.active_zone is None:
        decision = Decision(
            symbol=args.symbol,
            action=Action.HOLD,
            total_score=0,
            priority=Priority.NORMAL,
            reasons=["当日未接近日线 A/B 级关键价位"],
            next_step="继续观察，等待价格进入高优先级关键价位附近",
            cancel_condition="若后续接近日线 A/B 级关键价位，再重新评估15分钟卖出信号",
        )
    else:
        signals = run_intraday_monitor(daily_context, daily_bars, m15_bars)
        hard = evaluate_hard_rules(
            symbol=args.symbol,
            current_price=daily_context.current_price,
            position=position,
            rule=rules.get(args.symbol),
            signals=signals,
        )
        decision = hard or apply_support_protection(
            build_decision(args.symbol, compute_score(signals), signals),
            daily_context,
            daily_bars,
            m15_bars,
            signals,
        )

    print(f"Replay as of {args.as_of_date} 15:00:00")
    print(f"symbol: {args.symbol}")
    print(f"quote: {quote_price:.2f} @ {quote_ts.strftime('%Y-%m-%d %H:%M:%S')}")
    if daily_context.active_zone:
        zone = daily_context.active_zone
        print(f"active_zone: {zone.level.value} {zone.name} [{zone.low:.2f}, {zone.high:.2f}] tags={','.join(zone.tags)}")
    else:
        print("active_zone: none")
    for notice in notices:
        print(notice)
    print(format_decision(decision))
    return 0


def _load_replay_market_data(provider, symbol: str, as_of_dt: datetime):
    if hasattr(provider, "get_daily_bars_until") and hasattr(provider, "get_m15_bars_until"):
        daily_bars = provider.get_daily_bars_until(symbol, as_of_dt, limit=200)
        m15_bars = provider.get_m15_bars_until(symbol, as_of_dt, limit=200)
    else:
        daily_bars = [bar for bar in provider.get_daily_bars(symbol, limit=1000) if bar.ts <= as_of_dt][-200:]
        m15_bars = [bar for bar in provider.get_m15_bars(symbol, limit=1000) if bar.ts <= as_of_dt][-200:]

    if not daily_bars:
        raise MarketDataError(f"[{symbol}] 在 {as_of_dt.strftime('%Y-%m-%d')} 之前没有可用日线数据")

    quote_bar = m15_bars[-1] if m15_bars else daily_bars[-1]
    return daily_bars, m15_bars, quote_bar.close, quote_bar.ts


if __name__ == "__main__":
    raise SystemExit(main())
