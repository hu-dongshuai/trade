from __future__ import annotations

from pathlib import Path

from sell_monitor.domain.models import Position
from sell_monitor.storage.markdown_config import read_json_payload, write_json_payload


class JsonPositionStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_all(self) -> dict[str, Position]:
        if not self.path.exists():
            return {}
        data = read_json_payload(self.path)
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
        write_json_payload(self.path, payload, title="Positions")
        return created
