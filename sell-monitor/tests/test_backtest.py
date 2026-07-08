from __future__ import annotations

import unittest
from datetime import datetime

from sell_monitor.app.backtest import (
    BacktestEvent,
    OUTCOME_COVERED,
    OUTCOME_FALSE_POSITIVE,
    OUTCOME_HIT,
    OUTCOME_MISSED,
    OUTCOME_NO_TRIGGER,
    OUTCOME_UNDETERMINED,
    _adjust_missed_after_prior_sell_alerts,
    _classify_outcome,
    _dedupe_sell_alerts,
    _max_drawdown_pct,
    _max_runup_pct,
    summarize_events,
)
from sell_monitor.domain.enums import Action
from sell_monitor.domain.models import Bar


class BacktestTest(unittest.TestCase):
    def test_drawdown_and_runup_metrics(self) -> None:
        future = [
            Bar(datetime(2026, 5, 28), 100, 103, 96, 98, 1000),
            Bar(datetime(2026, 5, 29), 98, 101, 94, 95, 1000),
        ]

        self.assertEqual(6.0, _max_drawdown_pct(100, future))
        self.assertEqual(3.0, _max_runup_pct(100, future))

    def test_classifies_reduce_exit_and_missed_cases(self) -> None:
        self.assertEqual(OUTCOME_HIT, _classify_outcome(Action.REDUCE, 5.0, 1.0))
        self.assertEqual(OUTCOME_FALSE_POSITIVE, _classify_outcome(Action.REDUCE, 4.9, 7.2))
        self.assertEqual(OUTCOME_HIT, _classify_outcome(Action.EXIT_ALL, 7.0, 1.0))
        self.assertEqual(OUTCOME_FALSE_POSITIVE, _classify_outcome(Action.STOP_LOSS, 2.0, 7.5))
        self.assertEqual(OUTCOME_MISSED, _classify_outcome(Action.HOLD, 7.5, 0.0))
        self.assertEqual(OUTCOME_NO_TRIGGER, _classify_outcome(Action.HOLD, 1.0, 2.0))

    def test_summarizes_events(self) -> None:
        events = [
            BacktestEvent("A", "Sample A", "2026-01-01", Action.REDUCE, 4, 0, 10, 7.1, 0, OUTCOME_HIT, ""),
            BacktestEvent("A", "Sample A", "2026-01-02", Action.EXIT_ALL, 6, 0, 10, 7.2, 0, OUTCOME_HIT, ""),
            BacktestEvent("A", "Sample A", "2026-01-03", Action.HOLD, 0, 0, 10, 7.3, 0, OUTCOME_MISSED, ""),
        ]

        summary = summarize_events(events)

        self.assertEqual(1, summary["reduce_total"])
        self.assertEqual(1, summary["reduce_hit"])
        self.assertEqual(1, summary["exit_total"])
        self.assertEqual(1, summary["exit_hit"])
        self.assertEqual(1, summary["missed"])

    def test_prior_sell_alert_within_15_trading_days_prevents_missed_label(self) -> None:
        events = [
            BacktestEvent("A", "Sample A", "2026-01-01", Action.REDUCE, 4, 0, 10, 7.1, 0, OUTCOME_HIT, "reduce signal"),
            BacktestEvent("A", "Sample A", "2026-01-02", Action.HOLD, 0, 0, 10, 7.3, 0, OUTCOME_MISSED, "hold signal"),
        ]

        adjusted = _adjust_missed_after_prior_sell_alerts(events)

        self.assertEqual(OUTCOME_COVERED, adjusted[1].outcome)
        self.assertIn("不计为漏报", adjusted[1].reason)

    def test_dedupes_sell_alerts_and_keeps_higher_severity_in_window(self) -> None:
        events = [
            BacktestEvent("A", "Sample A", "2026-01-01", Action.REDUCE, 4, 0, 10, 0, 0, OUTCOME_HIT, "reduce"),
            BacktestEvent("A", "Sample A", "2026-01-03", Action.EXIT_ALL, 6, 0, 10, 0, 0, OUTCOME_HIT, "exit"),
            BacktestEvent("A", "Sample A", "2026-01-08", Action.HOLD, 0, 0, 10, 0, 0, OUTCOME_UNDETERMINED, "hold"),
        ]

        deduped = _dedupe_sell_alerts(events, window_days=5)

        self.assertEqual([Action.EXIT_ALL, Action.HOLD], [event.action for event in deduped])
        self.assertEqual("2026-01-03", deduped[0].as_of_date)


if __name__ == "__main__":
    unittest.main()
