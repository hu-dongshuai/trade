from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sell_monitor.config import AppConfig
from sell_monitor.storage.obsidian_watchlist_store import ObsidianWatchlistStore
from sell_monitor.storage.watchlist_factory import build_watchlist_store
from sell_monitor.storage.watchlist_store import JsonWatchlistStore


class WatchlistFactoryTest(unittest.TestCase):
    def test_returns_obsidian_store_for_sell_mode_when_sell_watchlist_is_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AppConfig(
                base_dir=root,
                examples_dir=root / "examples",
                cache_dir=root / "cache",
                watchlist_path=root / "legacy-watchlist.md",
                sell_watchlist_path=root / "sell-watchlist.md",
                entry_watchlist_path=root / "entry-watchlist.json",
                positions_path=root / "positions.json",
                user_rules_path=root / "rules.json",
                market_data_path=root / "market_data.json",
                provider="static",
                email=None,
                obsidian_monitor=None,
                obsidian_entry=None,
                miniqmt=None,
            )

            store = build_watchlist_store(config, mode="sell")

            self.assertIsInstance(store, ObsidianWatchlistStore)

    def test_returns_obsidian_store_for_entry_mode_when_entry_watchlist_is_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AppConfig(
                base_dir=root,
                examples_dir=root / "examples",
                cache_dir=root / "cache",
                watchlist_path=root / "legacy-watchlist.md",
                sell_watchlist_path=root / "sell-watchlist.json",
                entry_watchlist_path=root / "entry-watchlist.md",
                positions_path=root / "positions.json",
                user_rules_path=root / "rules.json",
                market_data_path=root / "market_data.json",
                provider="static",
                email=None,
                obsidian_monitor=None,
                obsidian_entry=None,
                miniqmt=None,
            )

            store = build_watchlist_store(config, mode="entry")

            self.assertIsInstance(store, ObsidianWatchlistStore)

    def test_returns_json_store_when_selected_watchlist_is_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = AppConfig(
                base_dir=root,
                examples_dir=root / "examples",
                cache_dir=root / "cache",
                watchlist_path=root / "legacy-watchlist.json",
                sell_watchlist_path=root / "sell-watchlist.json",
                entry_watchlist_path=root / "entry-watchlist.json",
                positions_path=root / "positions.json",
                user_rules_path=root / "rules.json",
                market_data_path=root / "market_data.json",
                provider="static",
                email=None,
                obsidian_monitor=None,
                obsidian_entry=None,
                miniqmt=None,
            )

            store = build_watchlist_store(config, mode="sell")

            self.assertIsInstance(store, JsonWatchlistStore)
