from __future__ import annotations

import json
from pathlib import Path

from sell_monitor.domain.models import Position


class JsonPositionStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_all(self) -> dict[str, Position]:
        data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        result: dict[str, Position] = {}
        for item in data["positions"]:
            result[item["symbol"]] = Position(
                symbol=item["symbol"],
                cost_price=float(item["cost_price"]),
                quantity=float(item["quantity"]),
            )
        return result

    def upsert(self, position: Position) -> bool:
        positions = self.load_all()
        created = position.symbol not in positions
        positions[position.symbol] = position
        payload = {
            "positions": [
                {
                    "symbol": item.symbol,
                    "cost_price": item.cost_price,
                    "quantity": item.quantity,
                }
                for item in positions.values()
            ]
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return created
