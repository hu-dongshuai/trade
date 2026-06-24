from __future__ import annotations

import json
from urllib import error, parse, request

from sell_monitor.config import TelegramConfig


class TelegramChannel:
    def __init__(self, config: TelegramConfig) -> None:
        self.config = config

    def send(self, subject: str, message: str) -> None:
        text = f"{subject}\n{message}".strip()
        payload = json.dumps(
            {
                "chat_id": self.config.chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        url = f"{self.config.api_base_url.rstrip('/')}/bot{self.config.bot_token}/sendMessage"
        req = request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=20) as response:
                response.read()
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Telegram send failed: HTTP {exc.code} {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Telegram send failed: {exc.reason}") from exc

