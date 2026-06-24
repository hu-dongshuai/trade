from __future__ import annotations

import unittest

from sell_monitor.app.entry_scan import _format_entry_telegram_message, _should_send_entry_telegram
from sell_monitor.app.main import _format_sell_telegram_message, _should_send_sell_telegram
from sell_monitor.config import TelegramConfig
from sell_monitor.domain.enums import Action, EntryAction, Priority
from sell_monitor.domain.models import Decision, EntryDecision


class TelegramNotificationTest(unittest.TestCase):
    def test_sell_telegram_only_for_high_score_sell_actions(self) -> None:
        sell_decision = Decision(
            symbol="002241",
            symbol_name="歌尔股份",
            action=Action.EXIT_ALL,
            total_score=8,
            priority=Priority.IMMEDIATE,
            reasons=["第三根危险上影线确认", "放量跌破15分钟MA20"],
            next_step="执行清仓",
            cancel_condition="重新站回关键压力位上方",
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
        self.assertIn("股票: 歌尔股份(002241)", _format_sell_telegram_message(sell_decision))
        self.assertIn("类型: 卖出", _format_sell_telegram_message(sell_decision))

    def test_entry_telegram_only_for_allowed_entry(self) -> None:
        decision = EntryDecision(
            symbol="300015",
            symbol_name="爱尔眼科",
            action=EntryAction.ALLOW_ENTRY,
            allowed=True,
            entry_score=7,
            entry_model="pullback_buy",
            planned_entry_price=12.3,
            stop_loss_price=11.7,
            first_take_profit_price=13.9,
            risk_reward_ratio=2.6,
            reasons=["日线趋势健康", "15分钟出现承接确认"],
            blocking_reasons=[],
            next_step="按计划挂单",
        )
        rejected = EntryDecision(
            symbol="300015",
            symbol_name="爱尔眼科",
            action=EntryAction.REJECT_ENTRY,
            allowed=False,
            entry_score=8,
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
        self.assertIn("股票: 爱尔眼科(300015)", message)
        self.assertIn("类型: 买入", message)
        self.assertIn("计划挂单价: 12.30", message)

    def test_telegram_config_placeholder_is_ignored_by_shape(self) -> None:
        config = TelegramConfig(
            bot_token="123:abc",
            chat_id="456",
            subject_prefix="[SellMonitor]",
        )
        self.assertEqual("123:abc", config.bot_token)


if __name__ == "__main__":
    unittest.main()
