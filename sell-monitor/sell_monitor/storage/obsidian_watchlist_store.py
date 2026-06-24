from __future__ import annotations

from pathlib import Path

from sell_monitor.storage.markdown_config import write_json_payload
from sell_monitor.storage.watchlist_store import JsonWatchlistStore


class ObsidianWatchlistStore(JsonWatchlistStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            write_json_payload(self.path, {"symbols": []}, title="Watchlist")
