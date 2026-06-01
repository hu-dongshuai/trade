from __future__ import annotations

from datetime import datetime
import unittest

from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import Decision, FundamentalSnapshot
from sell_monitor.scoring.fundamental_weight import apply_fundamental_weight, assess_fundamentals


class FundamentalWeightTest(unittest.TestCase):
    def test_strong_fundamental_downgrades_ordinary_reduce(self) -> None:
        assessment = assess_fundamentals(
            "TEST",
            FundamentalSnapshot(
                symbol="TEST",
                ts=datetime(2026, 5, 1),
                revenue_yoy=18,
                previous_revenue_yoy=12,
                deducted_net_profit_yoy=22,
                previous_deducted_net_profit_yoy=10,
                gross_margin=35,
                previous_gross_margin=34,
                net_margin=12,
                previous_net_margin=11,
                operating_cashflow_to_profit=1.1,
                roe=16,
                debt_asset_ratio=45,
                pe_percentile=55,
            ),
        )
        decision = Decision("TEST", Action.REDUCE, 4, Priority.HIGH, ["技术减仓"], "减仓", "信号消失")

        adjusted = apply_fundamental_weight(decision, assessment)

        self.assertEqual(assessment.level, "strong")
        self.assertEqual(adjusted.action, Action.HOLD)
        self.assertEqual(adjusted.total_score, 3)
        self.assertTrue(any("基本面强" in reason for reason in adjusted.reasons))

    def test_weak_fundamental_upgrades_hold_to_reduce(self) -> None:
        assessment = assess_fundamentals(
            "TEST",
            FundamentalSnapshot(
                symbol="TEST",
                ts=datetime(2026, 5, 1),
                revenue_yoy=-3,
                deducted_net_profit_yoy=-12,
                gross_margin=22,
                previous_gross_margin=26,
                net_margin=3,
                previous_net_margin=5,
                operating_cashflow_to_profit=0.4,
                roe=6,
                debt_asset_ratio=72,
            ),
        )
        decision = Decision("TEST", Action.HOLD, 3, Priority.NORMAL, ["技术观察"], "观察", "信号消失")

        adjusted = apply_fundamental_weight(decision, assessment)

        self.assertEqual(assessment.level, "weak")
        self.assertEqual(adjusted.action, Action.REDUCE)
        self.assertEqual(adjusted.total_score, 4)

    def test_event_risk_adds_two_points(self) -> None:
        assessment = assess_fundamentals(
            "TEST",
            FundamentalSnapshot(
                symbol="TEST",
                ts=datetime(2026, 5, 1),
                event_risk=True,
                event_note="业绩预告大幅下修",
            ),
        )

        self.assertEqual(assessment.level, "event_risk")
        self.assertEqual(assessment.score_adjustment, 2)
        self.assertIn("业绩预告大幅下修", assessment.reasons[0])


if __name__ == "__main__":
    unittest.main()
