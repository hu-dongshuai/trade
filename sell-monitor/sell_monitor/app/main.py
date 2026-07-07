from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sell_monitor.config import load_default_config
from sell_monitor.data.provider_factory import build_market_data_provider
from sell_monitor.domain.enums import Action
from sell_monitor.monitor.obsidian_backfill import backfill_missing_obsidian_records
from sell_monitor.monitor.sell_monitor_service import SellMonitorService
from sell_monitor.notifier.alert_dispatcher import ConsoleAlertDispatcher, ConsoleChannel
from sell_monitor.notifier.channels.email import EmailChannel
from sell_monitor.notifier.channels.obsidian import ObsidianMonitorRunRecorder
from sell_monitor.notifier.channels.telegram import TelegramChannel
from sell_monitor.notifier.symbol_display import display_symbol
from sell_monitor.review.alert_review_service import AlertReviewService, format_review_status
from sell_monitor.storage.alert_review_store import AlertReviewStore
from sell_monitor.storage.position_store import JsonPositionStore
from sell_monitor.storage.user_rule_store import JsonUserRuleStore
from sell_monitor.storage.watchlist_factory import build_watchlist_store
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
            f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] 非 A 股交易时段，跳过本轮实时检测。"
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
    alert_review_service = AlertReviewService(
        provider=provider,
        store=AlertReviewStore(config.cache_dir / "sell_alert_reviews.json"),
    )
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
    backfilled_sell_alerts: list[tuple[datetime, object]] = []

    def send_sell_telegram(decision) -> None:
        if not telegram_channel or not _should_send_sell_telegram(decision):
            return
        try:
            telegram_channel.send(
                subject=f"{config.telegram.subject_prefix} 卖出提醒 {display_symbol(decision.symbol, decision.symbol_name)} score={decision.total_score}",
                message=_format_sell_telegram_message(decision),
            )
        except Exception as exc:
            print(f"[Telegram] {display_symbol(decision.symbol, decision.symbol_name)} 发送失败: {exc}")

    def collect_backfilled_sell_alert(as_of_dt: datetime, decision) -> None:
        if _should_send_sell_telegram(decision):
            backfilled_sell_alerts.append((as_of_dt, decision))

    if obsidian_recorder:
        backfill_notices = backfill_missing_obsidian_records(
            provider=provider,
            recorder=obsidian_recorder,
            symbols=symbols,
            symbol_names=symbol_names,
            positions=position_store.load_all(),
            rules=user_rule_store.load_all(),
            current_time=current_time,
            on_backfilled_decision=collect_backfilled_sell_alert,
        )
        for notice in backfill_notices:
            print(notice)
        _send_backfill_sell_telegram_summaries(
            backfilled_sell_alerts,
            telegram_channel=telegram_channel,
            subject_prefix=config.telegram.subject_prefix if config.telegram else "[SellMonitor]",
        )

    try:
        result = service.run(symbol_filter=args.symbol)
    except Exception as exc:
        print(f"运行失败: {exc}")
        close = getattr(provider, "close", None)
        if callable(close):
            close()
        return 1

    all_notices: list[str] = []
    if hasattr(provider, "consume_notices"):
        all_notices.extend(provider.consume_notices())
        for notice in all_notices:
            print(notice)

    for notice in result.notices:
        all_notices.append(notice)
        print(notice)

    reviewed_alerts = alert_review_service.review_due_alerts(symbols=symbols)
    for alert in reviewed_alerts:
        review_notice = (
            f"[{alert.symbol}] {alert.alert_ts.strftime('%Y-%m-%d %H:%M:%S')} "
            f"{alert.action.value} 已完成 15 日复盘：{format_review_status(alert)}"
        )
        all_notices.append(review_notice)
        print(review_notice)

    alert_review_service.record_alerts(result.decisions, current_time)
    if obsidian_recorder:
        obsidian_recorder.apply_review_updates(reviewed_alerts)
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
        send_sell_telegram(decision)

    close = getattr(provider, "close", None)
    if callable(close):
        close()
    return 0


def _should_send_sell_telegram(decision) -> bool:
    return decision.action in {Action.REDUCE, Action.STOP_LOSS, Action.EXIT_ALL} and decision.total_score >= 5


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


def _send_backfill_sell_telegram_summaries(
    backfilled_sell_alerts: list[tuple[datetime, object]],
    telegram_channel,
    subject_prefix: str,
) -> None:
    if not telegram_channel or not backfilled_sell_alerts:
        return

    grouped: dict[str, list[tuple[datetime, object]]] = defaultdict(list)
    for as_of_dt, decision in backfilled_sell_alerts:
        grouped[decision.symbol].append((as_of_dt, decision))

    for _, items in grouped.items():
        items.sort(key=lambda item: item[0])
        latest_decision = items[-1][1]
        display = display_symbol(latest_decision.symbol, latest_decision.symbol_name)
        try:
            telegram_channel.send(
                subject=f"{subject_prefix} 回溯补齐卖出汇总 {display} count={len(items)}",
                message=_format_backfill_sell_telegram_summary(display, items),
            )
        except Exception as exc:
            print(f"[Telegram] {display} 回溯汇总发送失败: {exc}")


def _format_backfill_sell_telegram_summary(
    display: str,
    items: list[tuple[datetime, object]],
) -> str:
    first_ts = items[0][0].strftime("%Y-%m-%d %H:%M")
    last_ts = items[-1][0].strftime("%Y-%m-%d %H:%M")
    lines = [
        f"股票: {display}",
        "类型: 回溯补齐卖出汇总",
        f"条数: {len(items)}",
        f"时间范围: {first_ts} - {last_ts}",
        "明细:",
    ]
    max_items = 8
    for as_of_dt, decision in items[:max_items]:
        first_reason = decision.reasons[0] if decision.reasons else "无"
        lines.append(
            f"- {as_of_dt.strftime('%Y-%m-%d %H:%M')} {decision.action.value} score={decision.total_score} "
            f"price={_format_decision_price(decision)} reason={first_reason}"
        )
    if len(items) > max_items:
        lines.append(f"- 其余 {len(items) - max_items} 条已省略")
    return "\n".join(lines)


def _format_decision_price(decision) -> str:
    price = getattr(decision, "current_price", None)
    if price is None:
        return "-"
    return f"{price:.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
