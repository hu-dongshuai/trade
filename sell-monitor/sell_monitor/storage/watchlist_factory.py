from __future__ import annotations

from typing import Literal

from sell_monitor.config import AppConfig
from sell_monitor.storage.obsidian_watchlist_store import ObsidianWatchlistStore
from sell_monitor.storage.watchlist_store import JsonWatchlistStore


WatchlistMode = Literal["sell", "entry"]


def build_watchlist_store(config: AppConfig, mode: WatchlistMode = "sell") -> JsonWatchlistStore:
    path = config.sell_watchlist_path if mode == "sell" else config.entry_watchlist_path
    if path.suffix.lower() == ".md":
        return ObsidianWatchlistStore(path)
    return JsonWatchlistStore(path)
