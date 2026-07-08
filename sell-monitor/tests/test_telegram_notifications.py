from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import Mock

from sell_monitor.app.entry_scan import _format_entry_telegram_message, _should_send_entry_telegram
from sell_monitor.app.main import (
    _format_backfill_sell_telegram_summary,
    _format_sell_telegram_message,
    _send_backfill_sell_telegram_summaries,
    _should_send_sell_telegram,
)
from sell_monitor.config import TelegramConfig
from sell_monitor.domain.enums import Action, EntryAction, Priority
from sell_monitor.domain.models import Decision, EntryDecision


class TelegramNotificationTest(unittest.TestCase):
    def test_sell_telegram_only_for_high_score_sell_actions(self) -> None:
        sell_decision = Decision(
            symbol="002241",
            symbol_name="歌尔股份",
            action=Action.EXIT_ALL,
            total_score=5,
            priority=Priority.IMMEDIATE,
            reasons=["第三根危险上影线确认", "放量跌破15分钟MA20"],
            next_step="执行清仓",
            cancel_condition="重新站回关键压力位上方",
            current_price=21.56,
        )
        hold_decision = Decision(
            symbol="002241",
            symbol_name="歌尔股份",
            action=Action.HOLD,
            total_score=10,
            priority=Priority.NORMAL,
            reasons=["仅观察"],
            next_step="继续观察",
            cancel_condition="无",
        )

        self.assertTrue(_should_send_sell_telegram(sell_decision))
        self.assertFalse(_should_send_sell_telegram(hold_decision))

        message = _format_sell_telegram_message(sell_decision)
        self.assertIn("动作: exit_all", message)
        self.assertIn("价格: 21.56", message)
        self.assertIn("下一步: 执行清仓", message)
        self.assertIn("1. 第三根危险上影线确认", message)
        self.assertIn("2. 放量跌破15分钟MA20", message)
        self.assertNotIn("股票:", message)
        self.assertNotIn("类型:", message)

    def test_sell_telegram_threshold_is_five(self) -> None:
        below_threshold = Decision(
            symbol="002241",
            symbol_name="歌尔股份",
            action=Action.REDUCE,
            total_score=4,
            priority=Priority.HIGH,
            reasons=["测试"],
            next_step="观察",
            cancel_condition="无",
        )
        at_threshold = Decision(
            symbol="002241",
            symbol_name="歌尔股份",
            action=Action.REDUCE,
            total_score=5,
            priority=Priority.HIGH,
            reasons=["测试"],
            next_step="观察",
            cancel_condition="无",
        )

        self.assertFalse(_should_send_sell_telegram(below_threshold))
        self.assertTrue(_should_send_sell_telegram(at_threshold))

    def test_entry_telegram_only_for_allowed_entry(self) -> None:
        decision = EntryDecision(
            symbol="300015",
            symbol_name="爱尔眼科",
            action=EntryAction.ALLOW_ENTRY,
            allowed=True,
            entry_score=7,
            entry_route="standard_entry",
            entry_model="pullback_buy",
            planned_entry_price=12.3,
            stop_loss_price=11.7,
            first_take_profit_price=13.9,
            risk_reward_ratio=2.6,
            reasons=["日线趋势健康", "15分钟出现承接确认"],
            blocking_reasons=["上方有近端压力，需要轻仓试单"],
            next_step="按计划挂单，成交后严守止损",
        )
        rejected = EntryDecision(
            symbol="300015",
            symbol_name="爱尔眼科",
            action=EntryAction.REJECT_ENTRY,
            allowed=False,
            entry_score=8,
            entry_route="reject_reentry",
            entry_model="breakout_buy",
            planned_entry_price=12.8,
            stop_loss_price=12.0,
            first_take_profit_price=14.2,
            risk_reward_ratio=2.0,
            reasons=["结构不错"],
            blocking_reasons=["上方压力过近"],
            next_step="等待",
        )

        self.assertTrue(_should_send_entry_telegram(decision))
        self.assertFalse(_should_send_entry_telegram(rejected))

        message = _format_entry_telegram_message(decision)
        self.assertIn("路线: 标准开仓 / pullback_buy", message)
        self.assertIn("计划: 12.30", message)
        self.assertIn("止损: 11.70", message)
        self.assertIn("止盈1: 13.90", message)
        self.assertIn("盈亏比: 2.60", message)
        self.assertIn("1. 日线趋势健康", message)
        self.assertIn("2. 15分钟出现承接确认", message)
        self.assertIn("注意:\n1. 上方有近端压力，需要轻仓试单", message)
        self.assertNotIn("股票:", message)
        self.assertNotIn("类型:", message)

    def test_telegram_config_placeholder_is_ignored_by_shape(self) -> None:
        config = TelegramConfig(
            bot_token="123:abc",
            chat_id="456",
            subject_prefix="[SellMonitor]",
        )
        self.assertEqual("123:abc", config.bot_token)
        self.assertIsNone(config.proxy_url)

    def test_backfill_sell_notifications_are_grouped_per_symbol(self) -> None:
        decision_a = Decision(
            symbol="002241",
            symbol_name="歌尔股份",
            action=Action.EXIT_ALL,
            total_score=7,
            priority=Priority.IMMEDIATE,
            reasons=["第三根危险上影线确认", "14:15 这根15分钟K线放量跌破MA20"],
            next_step="清仓",
            cancel_condition="无",
            current_price=23.07,
        )
        decision_b = Decision(
            symbol="002241",
            symbol_name="歌尔股份",
            action=Action.REDUCE,
            total_score=5,
            priority=Priority.HIGH,
            reasons=["第一根危险上影线", "11:00 这根15分钟K线放量滞涨"],
            next_step="减仓",
            cancel_condition="无",
            current_price=23.60,
        )
        telegram_channel = Mock()

        _send_backfill_sell_telegram_summaries(
            [
                (datetime(2026, 6, 24, 9, 30), decision_a),
                (datetime(2026, 6, 24, 10, 30), decision_b),
            ],
            telegram_channel=telegram_channel,
            subject_prefix="[SellMonitor]",
        )

        telegram_channel.send.assert_called_once()
        subject = telegram_channel.send.call_args.kwargs["subject"]
        message = telegram_channel.send.call_args.kwargs["message"]
        self.assertIn("回溯卖出", subject)
        self.assertIn("2条", subject)
        self.assertIn("2026-06-24 09:30", message)
        self.assertIn("动作: exit_all", message)
        self.assertIn("1. 第三根危险上影线确认", message)
        self.assertIn("2. 14:15 这根15分钟K线放量跌破MA20", message)
        self.assertIn("2026-06-24 10:30", message)
        self.assertIn("动作: reduce", message)
        self.assertIn("2. 11:00 这根15分钟K线放量滞涨", message)

    def test_backfill_summary_formatter_limits_extra_rows(self) -> None:
        decision = Decision(
            symbol="002241",
            symbol_name="歌尔股份",
            action=Action.EXIT_ALL,
            total_score=7,
            priority=Priority.IMMEDIATE,
            reasons=["第三根危险上影线确认"],
            next_step="清仓",
            cancel_condition="无",
            current_price=23.07,
        )
        items = [(datetime(2026, 6, 24, 9, 30 + idx), decision) for idx in range(8)]
        items.append((datetime(2026, 6, 24, 13, 0), decision))

        message = _format_backfill_sell_telegram_summary("歌尔股份(002241)", items)

        self.assertIn("时间范围: 2026-06-24 09:30 - 2026-06-24 13:00", message)
        self.assertIn("其余 1 条已省略", message)


if __name__ == "__main__":
    unittest.main()
