from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sell_monitor.domain.enums import EntryAction
from sell_monitor.domain.models import DailyContext, EntryDecision, PriceZone
from sell_monitor.entry.entry_scan_service import EntryScanService
from sell_monitor.storage.watchlist_store import JsonWatchlistStore


class _ProviderWithDifferentName:
    def get_symbol_name(self, symbol: str) -> str:
        return f"Provider-{symbol}"

    def get_daily_bars(self, symbol: str, limit: int = 200):
        return []

    def get_m15_bars(self, symbol: str, limit: int = 200):
        return []


class EntryScanServiceTest(unittest.TestCase):
    def test_prefers_watchlist_name_over_provider_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "watchlist.json").write_text(
                json.dumps({"symbols": [{"symbol": "002241", "name": "歌尔股份"}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            store = JsonWatchlistStore(tmp_path / "watchlist.json")
            service = EntryScanService(data_provider=_ProviderWithDifferentName(), watchlist_store=store)

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
            decision = EntryDecision(
                symbol="002241",
                symbol_name="歌尔股份",
                action=EntryAction.WATCH_ENTRY,
                allowed=False,
                entry_score=4,
                entry_route="standard_entry",
                entry_model="pullback_buy",
                planned_entry_price=24.8,
                stop_loss_price=24.0,
                first_take_profit_price=26.0,
                risk_reward_ratio=1.5,
                reasons=["test"],
                blocking_reasons=[],
                next_step="继续观察",
            )

            with patch("sell_monitor.entry.entry_scan_service.build_daily_context", return_value=daily_context):
                with patch("sell_monitor.entry.entry_scan_service.build_entry_context", return_value=object()) as mocked_context:
                    with patch("sell_monitor.entry.entry_scan_service.detect_entry_candidates", return_value=[]):
                        with patch("sell_monitor.entry.entry_scan_service.build_entry_decision", return_value=decision):
                            service.run()

            self.assertEqual("歌尔股份", mocked_context.call_args.kwargs["symbol_name"])


if __name__ == "__main__":
    unittest.main()
