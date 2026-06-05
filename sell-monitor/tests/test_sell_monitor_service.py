from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sell_monitor.data.akshare_provider import MarketDataError
from sell_monitor.data.market_data_provider import StaticMarketDataProvider
from sell_monitor.monitor.sell_monitor_service import SellMonitorService
from sell_monitor.storage.position_store import JsonPositionStore
from sell_monitor.storage.user_rule_store import JsonUserRuleStore
from sell_monitor.storage.watchlist_store import JsonWatchlistStore


class _DummyNotifier:
    def dispatch(self, decision) -> None:
        return None


class _FailingProvider:
    def get_latest_quote(self, symbol: str):
        raise MarketDataError(f"[{symbol}] 行情获取失败：AkShare/东方财富接口暂时不可用，请稍后重试。")

    def get_daily_bars(self, symbol: str, limit: int = 200):
        raise MarketDataError(f"[{symbol}] 日线数据获取失败，请稍后重试。")

    def get_m15_bars(self, symbol: str, limit: int = 200):
        raise MarketDataError(f"[{symbol}] 15分钟数据获取失败，请稍后重试。")

    def get_market_state(self) -> str:
        return "neutral"

    def get_sector_state(self, symbol: str) -> str:
        return "neutral"


class SellMonitorServiceTest(unittest.TestCase):
    def test_watchlist_store_supports_symbol_name_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            watchlist_path = tmp_path / "watchlist.json"
            watchlist_path.write_text(
                json.dumps(
                    {
                        "symbols": [
                            {"symbol": "002241", "name": "歌尔股份"},
                            "300015",
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            store = JsonWatchlistStore(watchlist_path)

            self.assertEqual(["002241", "300015"], store.load())
            self.assertEqual({"002241": "歌尔股份"}, store.load_name_map())

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

        self.assertIn("[TESTA] 不在 watchlist.json 中，已自动加入", result.notices)
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

        self.assertIn("[002241] 行情获取失败：AkShare/东方财富接口暂时不可用，请稍后重试。", result.notices)
