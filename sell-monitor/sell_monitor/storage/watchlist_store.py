from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sell_monitor.storage.markdown_config import read_json_payload, write_json_payload


@dataclass(frozen=True)
class WatchlistItem:
    symbol: str
    name: str | None = None


class JsonWatchlistStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[str]:
        return [item.symbol for item in self.load_items()]

    def load_items(self) -> list[WatchlistItem]:
        data = read_json_payload(self.path)
        items: list[WatchlistItem] = []
        for raw in data["symbols"]:
            if isinstance(raw, str):
                items.append(WatchlistItem(symbol=raw))
                continue
            if isinstance(raw, dict):
                symbol = str(raw.get("symbol", "")).strip()
                if not symbol:
                    continue
                name = str(raw.get("name", "")).strip() or None
                items.append(WatchlistItem(symbol=symbol, name=name))
        return items

    def load_name_map(self) -> dict[str, str]:
        return {item.symbol: item.name for item in self.load_items() if item.name}

    def ensure_symbol(self, symbol: str) -> bool:
        items = self.load_items()
        if any(item.symbol == symbol for item in items):
            return False
        items.append(WatchlistItem(symbol=symbol))
        write_json_payload(
            self.path,
            {"symbols": _serialize_items(items)},
            title="Watchlist",
        )
        return True


def _serialize_items(items: list[WatchlistItem]) -> list[object]:
    payload: list[object] = []
    for item in items:
        if item.name:
            payload.append({"symbol": item.symbol, "name": item.name})
        else:
            payload.append(item.symbol)
    return payload
