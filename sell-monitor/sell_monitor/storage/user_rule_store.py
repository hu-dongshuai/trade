from __future__ import annotations

from pathlib import Path

from sell_monitor.domain.models import UserRule
from sell_monitor.storage.markdown_config import read_json_payload


class JsonUserRuleStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_all(self) -> dict[str, UserRule]:
        if not self.path.exists():
            return {}
        data = read_json_payload(self.path)
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
