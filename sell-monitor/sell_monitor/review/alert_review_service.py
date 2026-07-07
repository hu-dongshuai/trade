from __future__ import annotations

from datetime import datetime

from sell_monitor.domain.enums import Action
from sell_monitor.domain.models import AlertReviewRecord, Bar, Decision
from sell_monitor.storage.alert_review_store import AlertReviewStore, build_alert_id


SELL_ACTIONS = {Action.REDUCE, Action.EXIT_ALL, Action.STOP_LOSS}
FALSE_POSITIVE_THRESHOLD_PCT = 7.0


class AlertReviewService:
    def __init__(self, provider, store: AlertReviewStore, review_window_days: int = 5) -> None:
        self.provider = provider
        self.store = store
        self.review_window_days = review_window_days

    def record_alerts(self, decisions: list[Decision], alert_ts: datetime) -> list[AlertReviewRecord]:
        records = [
            AlertReviewRecord(
                alert_id=build_alert_id(decision.symbol, alert_ts, decision.action),
                symbol=decision.symbol,
                action=decision.action,
                alert_ts=alert_ts,
                price=float(decision.current_price or 0.0),
                score=decision.total_score,
                reasons=list(decision.reasons),
                symbol_name=decision.symbol_name,
                review_window_days=self.review_window_days,
            )
            for decision in decisions
            if decision.action in SELL_ACTIONS and decision.current_price is not None
        ]
        return self.store.append_missing(records)

    def review_due_alerts(self, symbols: list[str] | None = None) -> list[AlertReviewRecord]:
        records = self.store.load_all()
        symbol_filter = set(symbols or [])
        daily_cache: dict[str, list[Bar]] = {}
        updates: list[AlertReviewRecord] = []

        for record in records:
            if record.review_status != "pending":
                continue
            if symbol_filter and record.symbol not in symbol_filter:
                continue
            bars = daily_cache.get(record.symbol)
            if bars is None:
                try:
                    bars = self.provider.get_daily_bars(record.symbol, limit=5000)
                except Exception:
                    continue
                daily_cache[record.symbol] = bars
            future_daily = [bar for bar in bars if bar.ts.date() > record.alert_ts.date()][: record.review_window_days]
            if len(future_daily) < record.review_window_days:
                continue
            drawdown_pct = _max_drawdown_pct(record.price, future_daily)
            runup_pct = _max_runup_pct(record.price, future_daily)
            review_status = _classify_review(record.action, drawdown_pct, runup_pct)
            updates.append(
                self.store.mark_reviewed(
                    record,
                    review_status=review_status,
                    drawdown_pct=drawdown_pct,
                    runup_pct=runup_pct,
                    reviewed_at=future_daily[-1].ts,
                )
            )

        return self.store.replace_records(updates)


def format_review_status(record: AlertReviewRecord) -> str:
    if record.review_status == "pending":
        return "待复盘"
    if record.drawdown_pct is None or record.runup_pct is None:
        return _status_label(record.review_status)
    return (
        f"{_status_label(record.review_status)}"
        f"（5日涨{record.runup_pct:.2f}%/回{record.drawdown_pct:.2f}%）"
    )


def _status_label(review_status: str) -> str:
    mapping = {
        "hit": "命中",
        "false_positive": "误报",
        "watch": "待定",
        "pending": "待复盘",
    }
    return mapping.get(review_status, review_status)


def _classify_review(action: Action, drawdown_5d: float, runup_5d: float) -> str:
    if action in SELL_ACTIONS and drawdown_5d >= FALSE_POSITIVE_THRESHOLD_PCT:
        return "hit"
    if action in SELL_ACTIONS and runup_5d >= FALSE_POSITIVE_THRESHOLD_PCT:
        return "false_positive"
    return "watch"


def _max_drawdown_pct(price: float, future_daily: list[Bar]) -> float:
    if price <= 0 or not future_daily:
        return 0.0
    return max(0.0, (price - min(bar.low for bar in future_daily)) / price * 100)


def _max_runup_pct(price: float, future_daily: list[Bar]) -> float:
    if price <= 0 or not future_daily:
        return 0.0
    return max(0.0, (max(bar.high for bar in future_daily) - price) / price * 100)
