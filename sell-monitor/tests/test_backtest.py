from __future__ import annotations

import unittest
from datetime import datetime

from sell_monitor.app.backtest import (
    BacktestEvent,
    _adjust_missed_after_prior_sell_alerts,
    _classify_outcome,
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
        self.assertEqual("命中", _classify_outcome(Action.REDUCE, 7.1, 1.0))
        self.assertEqual("误报", _classify_outcome(Action.REDUCE, 6.9, 7.2))
        self.assertEqual("命中", _classify_outcome(Action.EXIT_ALL, 7.0, 1.0))
        self.assertEqual("误报", _classify_outcome(Action.STOP_LOSS, 2.0, 7.5))
        self.assertEqual("漏报", _classify_outcome(Action.HOLD, 7.5, 0.0))

    def test_summarizes_events(self) -> None:
        events = [
            BacktestEvent("A", "样本A", "2026-01-01", Action.REDUCE, 4, 10, 7.1, 0, "命中", ""),
            BacktestEvent("A", "样本A", "2026-01-02", Action.EXIT_ALL, 6, 10, 7.2, 0, "命中", ""),
            BacktestEvent("A", "样本A", "2026-01-03", Action.HOLD, 0, 10, 7.3, 0, "漏报", ""),
        ]

        summary = summarize_events(events)

        self.assertEqual(1, summary["reduce_total"])
        self.assertEqual(1, summary["reduce_hit"])
        self.assertEqual(1, summary["exit_total"])
        self.assertEqual(1, summary["exit_hit"])
        self.assertEqual(1, summary["missed"])

    def test_prior_sell_alert_within_15_trading_days_prevents_missed_label(self) -> None:
        events = [
            BacktestEvent("A", "样本A", "2026-01-01", Action.REDUCE, 4, 10, 7.1, 0, "命中", "减仓信号"),
            BacktestEvent("A", "样本A", "2026-01-02", Action.HOLD, 0, 10, 7.3, 0, "漏报", "持有信号"),
        ]

        adjusted = _adjust_missed_after_prior_sell_alerts(events)

        self.assertEqual("已预警", adjusted[1].outcome)
        self.assertIn("不计为漏报", adjusted[1].reason)


if __name__ == "__main__":
    unittest.main()
