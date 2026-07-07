from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from sell_monitor.domain.enums import Action
from sell_monitor.domain.models import AlertReviewRecord


class AlertReviewStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> list[AlertReviewRecord]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [_record_from_payload(item) for item in payload]

    def save_all(self, records: list[AlertReviewRecord]) -> None:
        payload = [_record_to_payload(record) for record in records]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_missing(self, records: list[AlertReviewRecord]) -> list[AlertReviewRecord]:
        existing = self.load_all()
        existing_ids = {record.alert_id for record in existing}
        appended = [record for record in records if record.alert_id not in existing_ids]
        if not appended:
            return []
        self.save_all(existing + appended)
        return appended

    def replace_records(self, updates: list[AlertReviewRecord]) -> list[AlertReviewRecord]:
        if not updates:
            return []
        update_map = {record.alert_id: record for record in updates}
        existing = self.load_all()
        changed = False
        replaced: list[AlertReviewRecord] = []
        merged: list[AlertReviewRecord] = []
        for record in existing:
            updated = update_map.get(record.alert_id)
            if updated is None:
                merged.append(record)
                continue
            merged.append(updated)
            replaced.append(updated)
            changed = True
        if changed:
            self.save_all(merged)
        return replaced

    def mark_reviewed(
        self,
        record: AlertReviewRecord,
        review_status: str,
        drawdown_pct: float,
        runup_pct: float,
        reviewed_at: datetime,
    ) -> AlertReviewRecord:
        return replace(
            record,
            review_status=review_status,
            drawdown_pct=drawdown_pct,
            runup_pct=runup_pct,
            reviewed_at=reviewed_at,
        )


def build_alert_id(symbol: str, alert_ts: datetime, action: Action) -> str:
    return f"{symbol}:{alert_ts.isoformat()}:{action.value}"


def _record_from_payload(payload: dict) -> AlertReviewRecord:
    reviewed_at = payload.get("reviewed_at")
    return AlertReviewRecord(
        alert_id=str(payload["alert_id"]),
        symbol=str(payload["symbol"]),
        action=Action(str(payload["action"])),
        alert_ts=datetime.fromisoformat(str(payload["alert_ts"])),
        price=float(payload["price"]),
        score=int(payload["score"]),
        reasons=[str(item) for item in payload.get("reasons", [])],
        symbol_name=(str(payload["symbol_name"]) if payload.get("symbol_name") else None),
        review_window_days=int(payload.get("review_window_days", 5)),
        review_status=str(payload.get("review_status", "pending")),
        reviewed_at=(datetime.fromisoformat(str(reviewed_at)) if reviewed_at else None),
        drawdown_pct=(float(payload["drawdown_pct"]) if payload.get("drawdown_pct") is not None else None),
        runup_pct=(float(payload["runup_pct"]) if payload.get("runup_pct") is not None else None),
    )


def _record_to_payload(record: AlertReviewRecord) -> dict:
    return {
        "alert_id": record.alert_id,
        "symbol": record.symbol,
        "action": record.action.value,
        "alert_ts": record.alert_ts.isoformat(),
        "price": record.price,
        "score": record.score,
        "reasons": list(record.reasons),
        "symbol_name": record.symbol_name,
        "review_window_days": record.review_window_days,
        "review_status": record.review_status,
        "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
        "drawdown_pct": record.drawdown_pct,
        "runup_pct": record.runup_pct,
    }
