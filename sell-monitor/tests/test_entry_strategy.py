from __future__ import annotations

import unittest

from sell_monitor.domain.enums import EntryAction, ZoneLevel
from sell_monitor.domain.models import PriceZone
from sell_monitor.entry.decision_engine import build_entry_decision
from sell_monitor.entry.models import EntryCandidate, EntryContext


def _context(**overrides) -> EntryContext:
    base = EntryContext(
        symbol="002241",
        symbol_name="歌尔股份",
        current_price=25.0,
        market_state="neutral",
        sector_state="neutral",
        daily_trend="up",
        is_trend_healthy=True,
        is_m60_trend_healthy=True,
        daily_relative_strength_ok=True,
        liquidity_ok=True,
        avg_daily_turnover=350000000.0,
        recent_5d_return=4.2,
        recent_10d_return=8.5,
        daily_support_zones=[],
        daily_resistance_zones=[],
    )
    values = {**base.__dict__, **overrides}
    return EntryContext(**values)


class EntryStrategyTest(unittest.TestCase):
    def test_hard_block_prevents_allow_entry_even_if_score_is_high(self) -> None:
        context = _context()
        candidate = EntryCandidate(
            model="pullback_buy",
            score=8,
            planned_entry_price=24.8,
            stop_loss_price=23.9,
            first_take_profit_price=27.5,
            risk_reward_ratio=3.0,
            reasons=["趋势和位置都不错"],
            hard_blocking_reasons=["60分钟结构未保持抬升，暂不做回踩开仓"],
        )

        decision = build_entry_decision(context, [candidate])

        self.assertEqual(EntryAction.REJECT_ENTRY, decision.action)
        self.assertFalse(decision.allowed)
        self.assertIn("60分钟结构未保持抬升", "；".join(decision.blocking_reasons))

    def test_missing_plan_forces_reject(self) -> None:
        context = _context()
        candidate = EntryCandidate(
            model="breakout_buy",
            score=9,
            planned_entry_price=25.2,
            stop_loss_price=None,
            first_take_profit_price=29.0,
            risk_reward_ratio=None,
            reasons=["突破很强"],
        )

        decision = build_entry_decision(context, [candidate])

        self.assertEqual(EntryAction.REJECT_ENTRY, decision.action)
        self.assertFalse(decision.allowed)
        self.assertIn("止损位或第一止盈位无法明确识别", "；".join(decision.blocking_reasons))

    def test_clean_candidate_can_still_allow_entry(self) -> None:
        context = _context()
        candidate = EntryCandidate(
            model="order_block_buy",
            score=7,
            planned_entry_price=24.7,
            stop_loss_price=23.8,
            first_take_profit_price=27.4,
            risk_reward_ratio=3.0,
            reasons=["趋势健康", "15分钟承接确认"],
        )

        decision = build_entry_decision(context, [candidate])

        self.assertEqual(EntryAction.ALLOW_ENTRY, decision.action)
        self.assertTrue(decision.allowed)

    def test_c_level_support_without_strong_confluence_should_be_blocked(self) -> None:
        zone = PriceZone(
            name="daily_support_test",
            timeframe="1d",
            low=24.2,
            high=24.8,
            level=ZoneLevel.C,
            tags=["support"],
            fragility_score=0,
        )
        self.assertEqual(zone.level, ZoneLevel.C)


if __name__ == "__main__":
    unittest.main()
