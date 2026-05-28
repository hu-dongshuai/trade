from __future__ import annotations

import json
from pathlib import Path


class JsonWatchlistStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[str]:
        data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        return list(data["symbols"])

    def ensure_symbol(self, symbol: str) -> bool:
        symbols = self.load()
        if symbol in symbols:
            return False
        symbols.append(symbol)
        self.path.write_text(
            json.dumps({"symbols": symbols}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
