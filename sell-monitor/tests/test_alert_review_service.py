from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Bar, Decision
from sell_monitor.review.alert_review_service import AlertReviewService
from sell_monitor.storage.alert_review_store import AlertReviewStore


class _StubProvider:
    def __init__(self, bars_by_symbol: dict[str, list[Bar]]) -> None:
        self.bars_by_symbol = bars_by_symbol

    def get_daily_bars(self, symbol: str, limit: int = 5000) -> list[Bar]:
        return self.bars_by_symbol[symbol][-limit:]


def _bars(start_price: float, deltas: list[tuple[float, float]]) -> list[Bar]:
    start = datetime(2026, 6, 1)
    bars: list[Bar] = []
    price = start_price
    for idx, (low_delta, high_delta) in enumerate(deltas):
        bars.append(
            Bar(
                ts=start + timedelta(days=idx),
                open=price,
                high=price * (1 + high_delta / 100),
                low=price * (1 - low_delta / 100),
                close=price,
                volume=1000,
            )
        )
    return bars


class AlertReviewServiceTest(unittest.TestCase):
    def test_records_pending_sell_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AlertReviewStore(Path(tmp) / "reviews.json")
            service = AlertReviewService(_StubProvider({"002241": []}), store)
            decision = Decision(
                symbol="002241",
                symbol_name="歌尔股份",
                action=Action.EXIT_ALL,
                total_score=8,
                priority=Priority.IMMEDIATE,
                reasons=["出现第三根危险上影线"],
                next_step="清仓",
                cancel_condition="重新站回关键价位",
                current_price=24.90,
            )

            recorded = service.record_alerts([decision], datetime(2026, 6, 24, 10, 30, 0))

            self.assertEqual(1, len(recorded))
            self.assertEqual("pending", recorded[0].review_status)
            self.assertEqual("002241", recorded[0].symbol)

    def test_reviews_false_positive_after_five_future_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bars = _bars(
                24.90,
                [
                    (0.0, 0.0),
                    (1.0, 3.0),
                    (1.5, 5.0),
                    (1.0, 7.5),
                    (2.0, 8.2),
                    (1.2, 9.0),
                ],
            )
            provider = _StubProvider({"002241": bars})
            store = AlertReviewStore(Path(tmp) / "reviews.json")
            service = AlertReviewService(provider, store)
            decision = Decision(
                symbol="002241",
                symbol_name="歌尔股份",
                action=Action.EXIT_ALL,
                total_score=8,
                priority=Priority.IMMEDIATE,
                reasons=["出现第三根危险上影线"],
                next_step="清仓",
                cancel_condition="重新站回关键价位",
                current_price=24.90,
            )
            service.record_alerts([decision], datetime(2026, 6, 1, 15, 0, 0))

            reviewed = service.review_due_alerts(symbols=["002241"])

            self.assertEqual(1, len(reviewed))
            self.assertEqual("false_positive", reviewed[0].review_status)
            self.assertGreaterEqual(reviewed[0].runup_pct or 0.0, 7.0)
            self.assertLess(reviewed[0].drawdown_pct or 100.0, 7.0)


if __name__ == "__main__":
    unittest.main()
