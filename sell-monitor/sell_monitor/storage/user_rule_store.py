from __future__ import annotations

import json
from pathlib import Path

from sell_monitor.domain.models import UserRule


class JsonUserRuleStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_all(self) -> dict[str, UserRule]:
        data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        result: dict[str, UserRule] = {}
        for item in data["rules"]:
            result[item["symbol"]] = UserRule(
                symbol=item["symbol"],
                stop_loss=item.get("stop_loss"),
                take_profit=item.get("take_profit"),
                hard_exit_note=item.get("hard_exit_note"),
                entry_reason=item.get("entry_reason"),
            )
        return result
