from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.market_data_provider import StaticMarketDataProvider
from sell_monitor.domain.enums import Action, Priority
from sell_monitor.domain.models import DailyContext, Decision, PriceZone, Signal
from sell_monitor.monitor.sell_monitor_service import SellMonitorService
from sell_monitor.storage.position_store import JsonPositionStore
from sell_monitor.storage.user_rule_store import JsonUserRuleStore
from sell_monitor.storage.watchlist_store import JsonWatchlistStore


class _DummyNotifier:
    def dispatch(self, decision) -> None:
        return None


class _FailingProvider:
    def get_latest_quote(self, symbol: str):
        raise MarketDataError(f"[{symbol}] 行情获取失败，请稍后重试。")

    def get_daily_bars(self, symbol: str, limit: int = 200):
        raise MarketDataError(f"[{symbol}] 日线数据获取失败，请稍后重试。")

    def get_m15_bars(self, symbol: str, limit: int = 200):
        raise MarketDataError(f"[{symbol}] 15分钟数据获取失败，请稍后重试。")

    def get_market_state(self) -> str:
        return "neutral"

    def get_sector_state(self, symbol: str) -> str:
        return "neutral"


class _ProviderWithDifferentName(_FailingProvider):
    def get_symbol_name(self, symbol: str) -> str:
        return f"Provider-{symbol}"

    def get_daily_bars(self, symbol: str, limit: int = 200):
        return []

    def get_m15_bars(self, symbol: str, limit: int = 200):
        return []


class SellMonitorServiceTest(unittest.TestCase):
    def test_watchlist_store_supports_symbol_name_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            watchlist_path = tmp_path / "watchlist.json"
            watchlist_path.write_text(
                json.dumps(
                    {
                        "symbols": [
                            {"symbol": "002241", "name": "姝屽皵鑲′唤"},
                            "300015",
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            store = JsonWatchlistStore(watchlist_path)

            self.assertEqual(["002241", "300015"], store.load())
            self.assertEqual({"002241": "姝屽皵鑲′唤"}, store.load_name_map())

    def test_runs_without_positions_file(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        provider = StaticMarketDataProvider(project_root / "examples" / "market_data.json")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "watchlist.json").write_text(
                json.dumps({"symbols": ["TESTA"]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (tmp_path / "user_rules.json").write_text(
                json.dumps({"rules": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            service = SellMonitorService(
                data_provider=provider,
                watchlist_store=JsonWatchlistStore(tmp_path / "watchlist.json"),
                position_store=JsonPositionStore(tmp_path / "positions.json"),
                user_rule_store=JsonUserRuleStore(tmp_path / "user_rules.json"),
                notifier=_DummyNotifier(),
            )

            result = service.run()

        self.assertEqual([], result.notices)
        self.assertEqual(1, len(result.decisions))

    def test_static_provider_missing_symbol_raises_friendly_market_data_error(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        provider = StaticMarketDataProvider(project_root / "examples" / "market_data.json")

        with self.assertRaises(MarketDataError) as context:
            provider.get_daily_bars("002241")

        self.assertIn("static", str(context.exception))
        self.assertIn("akshare/baostock", str(context.exception))

    def test_auto_adds_symbol_to_watchlist_when_filtered(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        provider = StaticMarketDataProvider(project_root / "examples" / "market_data.json")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "watchlist.json").write_text(
                json.dumps({"symbols": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            (tmp_path / "user_rules.json").write_text(
                json.dumps({"rules": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            service = SellMonitorService(
                data_provider=provider,
                watchlist_store=JsonWatchlistStore(tmp_path / "watchlist.json"),
                position_store=JsonPositionStore(tmp_path / "positions.json"),
                user_rule_store=JsonUserRuleStore(tmp_path / "user_rules.json"),
                notifier=_DummyNotifier(),
            )

            result = service.run(symbol_filter="TESTA")
            watchlist_data = json.loads((tmp_path / "watchlist.json").read_text(encoding="utf-8"))

        self.assertTrue(any("TESTA" in notice for notice in result.notices))
        self.assertIn("TESTA", watchlist_data["symbols"])

    def test_returns_friendly_notice_when_market_data_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "watchlist.json").write_text(
                json.dumps({"symbols": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            (tmp_path / "user_rules.json").write_text(
                json.dumps({"rules": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            service = SellMonitorService(
                data_provider=_FailingProvider(),
                watchlist_store=JsonWatchlistStore(tmp_path / "watchlist.json"),
                position_store=JsonPositionStore(tmp_path / "positions.json"),
                user_rule_store=JsonUserRuleStore(tmp_path / "user_rules.json"),
                notifier=_DummyNotifier(),
            )

            result = service.run(symbol_filter="002241")

        self.assertTrue(any("002241" in notice and "获取失败" in notice for notice in result.notices))

class SellMonitorServiceNamePreferenceTest(unittest.TestCase):
    def test_prefers_watchlist_name_over_provider_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "watchlist.json").write_text(
                json.dumps({"symbols": [{"symbol": "002241", "name": "歌尔股份"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (tmp_path / "user_rules.json").write_text(
                json.dumps({"rules": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            service = SellMonitorService(
                data_provider=_ProviderWithDifferentName(),
                watchlist_store=JsonWatchlistStore(tmp_path / "watchlist.json"),
                position_store=JsonPositionStore(tmp_path / "positions.json"),
                user_rule_store=JsonUserRuleStore(tmp_path / "user_rules.json"),
                notifier=_DummyNotifier(),
            )

            daily_context = DailyContext(
                symbol="002241",
                current_price=25.0,
                daily_zones=[PriceZone(name="support", timeframe="1d", low=24.0, high=26.0, tags=["support"])],
                active_zone=PriceZone(name="support", timeframe="1d", low=24.0, high=26.0, tags=["support"]),
                daily_trend="up",
                market_state="neutral",
                sector_state="neutral",
                daily_bars=[],
            )
            with patch("sell_monitor.monitor.sell_monitor_service.build_daily_context", return_value=daily_context):
                with patch("sell_monitor.monitor.sell_monitor_service.run_intraday_monitor", return_value=[]):
                    with patch("sell_monitor.monitor.sell_monitor_service.evaluate_hard_rules", return_value=None):
                        with patch("sell_monitor.monitor.sell_monitor_service.compute_score", return_value=0):
                            result = service.run()

            self.assertEqual("歌尔股份", result.decisions[0].symbol_name)

    def test_warning_state_allows_monitoring_without_active_zone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "watchlist.json").write_text(
                json.dumps({"symbols": [{"symbol": "002241", "name": "歌尔股份"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (tmp_path / "user_rules.json").write_text(
                json.dumps({"rules": []}, ensure_ascii=False),
                encoding="utf-8",
            )

            service = SellMonitorService(
                data_provider=_ProviderWithDifferentName(),
                watchlist_store=JsonWatchlistStore(tmp_path / "watchlist.json"),
                position_store=JsonPositionStore(tmp_path / "positions.json"),
                user_rule_store=JsonUserRuleStore(tmp_path / "user_rules.json"),
                notifier=_DummyNotifier(),
            )

            daily_context = DailyContext(
                symbol="002241",
                current_price=25.0,
                daily_zones=[PriceZone(name="support", timeframe="1d", low=24.0, high=26.0, tags=["support"])],
                active_zone=None,
                daily_trend="down",
                market_state="neutral",
                sector_state="neutral",
                daily_bars=[],
            )
            warned_context = DailyContext(
                symbol="002241",
                current_price=25.0,
                daily_zones=daily_context.daily_zones,
                active_zone=None,
                daily_trend="down",
                market_state="neutral",
                sector_state="neutral",
                daily_bars=[],
                sell_warning_active=True,
                sell_warning_reasons=["日线收盘跌破 MA20，且 MA20 已走平或开始拐头", "60分钟结构转弱，出现更低高点和更低低点"],
            )
            with patch("sell_monitor.monitor.sell_monitor_service.build_daily_context", return_value=daily_context):
                with patch("sell_monitor.monitor.sell_monitor_service.with_sell_warning_state", return_value=warned_context):
                    with patch("sell_monitor.monitor.sell_monitor_service.run_intraday_monitor", return_value=[Signal("structure_break", 2, True, "跌破最近一次创出新高后的回调低点")]):
                        with patch("sell_monitor.monitor.sell_monitor_service.evaluate_hard_rules", return_value=None):
                            with patch("sell_monitor.monitor.sell_monitor_service.compute_score", return_value=2):
                                result = service.run()

            self.assertEqual(1, len(result.decisions))
            self.assertEqual(Action.HOLD, result.decisions[0].action)

