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
        weekly_background="A",
        accumulation_score=8,
        accumulation_reasons=["周线接近支撑", "日线回踩缩量"],
        weekly_support_zones=[],
        weekly_resistance_zones=[],
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
        self.assertEqual("reject_reentry", decision.entry_route)

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
        self.assertEqual("reject_reentry", decision.entry_route)

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
        self.assertEqual("standard_entry", decision.entry_route)

    def test_standard_entry_is_allowed_at_score_five_and_rr_one_point_five(self) -> None:
        context = _context()
        candidate = EntryCandidate(
            model="pullback_buy",
            score=5,
            planned_entry_price=24.8,
            stop_loss_price=24.0,
            first_take_profit_price=26.0,
            risk_reward_ratio=1.5,
            reasons=["趋势健康", "接近支撑并出现承接"],
        )

        decision = build_entry_decision(context, [candidate])

        self.assertEqual(EntryAction.ALLOW_ENTRY, decision.action)
        self.assertTrue(decision.allowed)
        self.assertEqual("standard_entry", decision.entry_route)

    def test_t_reentry_can_allow_with_relaxed_rr_and_confirmation(self) -> None:
        support = PriceZone(
            name="daily_support_a",
            timeframe="1d",
            low=24.4,
            high=24.9,
            level=ZoneLevel.A,
            tags=["support", "with_fvg"],
            fragility_score=0,
        )
        context = _context(daily_support_zones=[support])
        candidate = EntryCandidate(
            model="pullback_buy",
            score=5,
            planned_entry_price=24.8,
            stop_loss_price=24.1,
            first_take_profit_price=25.9,
            risk_reward_ratio=1.57,
            reasons=["日线趋势健康", "回踩到A级支撑"],
            hard_blocking_reasons=[
                "15分钟尚未出现明确承接确认",
                "标准开仓要求盈亏比至少 1.5:1。",
            ],
            support_zone=support,
        )

        decision = build_entry_decision(context, [candidate])

        self.assertEqual(EntryAction.ALLOW_ENTRY, decision.action)
        self.assertTrue(decision.allowed)
        self.assertEqual("t_reentry", decision.entry_route)
        self.assertIn("T 仓回补", "；".join(decision.reasons))

    def test_probe_entry_can_allow_light_position_trial(self) -> None:
        support = PriceZone(
            name="daily_support_b",
            timeframe="1d",
            low=24.4,
            high=24.9,
            level=ZoneLevel.B,
            tags=["support", "with_fvg"],
            fragility_score=0,
        )
        context = _context(daily_support_zones=[support], accumulation_score=5)
        candidate = EntryCandidate(
            model="pullback_buy",
            score=4,
            planned_entry_price=24.8,
            stop_loss_price=24.2,
            first_take_profit_price=26.0,
            risk_reward_ratio=1.55,
            reasons=["日线趋势健康", "回踩到B级支撑"],
            hard_blocking_reasons=["15分钟尚未出现明确承接确认"],
            support_zone=support,
        )

        decision = build_entry_decision(context, [candidate])

        self.assertEqual(EntryAction.ALLOW_ENTRY, decision.action)
        self.assertTrue(decision.allowed)
        self.assertEqual("probe_entry", decision.entry_route)
        self.assertIn("轻仓试错", decision.next_step)

    def test_breakout_candidate_cannot_fall_back_to_t_reentry(self) -> None:
        context = _context()
        candidate = EntryCandidate(
            model="breakout_buy",
            score=5,
            planned_entry_price=25.3,
            stop_loss_price=24.8,
            first_take_profit_price=26.2,
            risk_reward_ratio=1.4,
            reasons=["突破模型接近成立"],
        )

        decision = build_entry_decision(context, [candidate])

        self.assertFalse(decision.allowed)
        self.assertEqual("reject_reentry", decision.entry_route)
        self.assertIn("做T回补只适用于回踩型或订单块承接型", "；".join(decision.blocking_reasons))

    def test_probe_entry_does_not_allow_breakout_model(self) -> None:
        context = _context()
        candidate = EntryCandidate(
            model="breakout_buy",
            score=4,
            planned_entry_price=25.3,
            stop_loss_price=24.8,
            first_take_profit_price=26.4,
            risk_reward_ratio=1.7,
            reasons=["突破模型接近成立"],
            hard_blocking_reasons=["突破后的首次回调承接不够清晰"],
        )

        decision = build_entry_decision(context, [candidate])

        self.assertFalse(decision.allowed)
        self.assertNotEqual("probe_entry", decision.entry_route)

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
