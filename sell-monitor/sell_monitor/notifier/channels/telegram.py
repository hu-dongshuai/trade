from __future__ import annotations

import json
from urllib import error, request

from sell_monitor.config import TelegramConfig


class TelegramChannel:
    def __init__(self, config: TelegramConfig) -> None:
        self.config = config

    def send(self, subject: str, message: str) -> None:
        text = f"{subject}\n{message}".strip()
        if self._send_with_requests(text):
            return
        self._send_with_urllib(text)

    def _send_with_requests(self, text: str) -> bool:
        try:
            import requests  # type: ignore
        except Exception:
            return False
        proxies = None
        if self.config.proxy_url:
            proxies = {
                "http": self.config.proxy_url,
                "https": self.config.proxy_url,
            }
        response = requests.post(
            f"{self.config.api_base_url.rstrip('/')}/bot{self.config.bot_token}/sendMessage",
            json={
                "chat_id": self.config.chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            proxies=proxies,
            timeout=20,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # type: ignore[attr-defined]
            raise RuntimeError(f"Telegram send failed: HTTP {response.status_code} {response.text}") from exc
        return True

    def _send_with_urllib(self, text: str) -> None:
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
        opener = self._build_opener()
        try:
            with opener.open(req, timeout=20) as response:
                response.read()
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Telegram send failed: HTTP {exc.code} {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Telegram send failed: {exc.reason}") from exc

    def _build_opener(self):
        if self.config.proxy_url:
            proxy_handler = request.ProxyHandler(
                {
                    "http": self.config.proxy_url,
                    "https": self.config.proxy_url,
                }
            )
            return request.build_opener(proxy_handler)
        return request.build_opener()
