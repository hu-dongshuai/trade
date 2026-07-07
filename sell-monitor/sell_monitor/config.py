from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from sell_monitor.storage.markdown_config import parse_env_text


DEFAULT_OBSIDIAN_MONITOR_ROOT = Path(r"E:\tools\OB\Obsidian\Trade\notes\monitor")
DEFAULT_OBSIDIAN_CONFIG_DIR = DEFAULT_OBSIDIAN_MONITOR_ROOT / "config"
DEFAULT_OBSIDIAN_SELL_DIR = DEFAULT_OBSIDIAN_MONITOR_ROOT / "sell"
DEFAULT_OBSIDIAN_ENTRY_DIR = DEFAULT_OBSIDIAN_MONITOR_ROOT / "entry"
DEFAULT_OBSIDIAN_ENV_PATH = DEFAULT_OBSIDIAN_CONFIG_DIR / "sell-monitor-config.md"
DEFAULT_SELL_WATCHLIST_PATH = DEFAULT_OBSIDIAN_CONFIG_DIR / "sell-watchlist.md"
DEFAULT_ENTRY_WATCHLIST_PATH = DEFAULT_OBSIDIAN_CONFIG_DIR / "entry-watchlist.md"


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: str
    smtp_port: int
    username: str
    password: str
    from_addr: str
    to_addr: str
    use_tls: bool = True
    subject_prefix: str = "[SellMonitor]"


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str
    subject_prefix: str = "[SellMonitor]"
    api_base_url: str = "https://api.telegram.org"
    proxy_url: str | None = None


@dataclass(frozen=True)
class ObsidianMonitorConfig:
    monitor_dir: Path


@dataclass(frozen=True)
class ObsidianEntryConfig:
    monitor_dir: Path


@dataclass(frozen=True)
class MiniQmtConfig:
    userdata_path: Path


@dataclass(frozen=True)
class AppConfig:
    base_dir: Path
    examples_dir: Path
    cache_dir: Path
    watchlist_path: Path
    sell_watchlist_path: Path
    entry_watchlist_path: Path
    positions_path: Path
    user_rules_path: Path
    market_data_path: Path
    provider: str
    email: EmailConfig | None
    telegram: TelegramConfig | None
    obsidian_monitor: ObsidianMonitorConfig | None
    obsidian_entry: ObsidianEntryConfig | None
    miniqmt: MiniQmtConfig | None


def _resolve_env_file_path(root: Path) -> Path:
    explicit = os.getenv("SELL_MONITOR_ENV_FILE", "").strip()
    if explicit:
        return Path(explicit)
    if DEFAULT_OBSIDIAN_ENV_PATH.exists():
        return DEFAULT_OBSIDIAN_ENV_PATH
    md_fallback = DEFAULT_OBSIDIAN_CONFIG_DIR / "sell-monitor.env"
    if md_fallback.exists():
        return md_fallback
    return root / ".env"


def _load_env_file(root: Path) -> None:
    env_path = _resolve_env_file_path(root)
    if not env_path.exists():
        return
    for raw_line in parse_env_text(env_path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _read_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_path_env(*names: str, default: Path) -> Path:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return Path(value)
    return default


def _load_email_config() -> EmailConfig | None:
    smtp_host = os.getenv("SELL_MONITOR_SMTP_HOST")
    if not smtp_host:
        return None
    smtp_host = smtp_host.strip()
    if smtp_host.lower() in {"smtp.example.com", "example.com"}:
        return None
    from_addr = os.getenv("SELL_MONITOR_EMAIL_FROM", "").strip()
    to_addr = os.getenv("SELL_MONITOR_EMAIL_TO", "").strip()
    if not from_addr or not to_addr:
        return None
    return EmailConfig(
        smtp_host=smtp_host,
        smtp_port=int(os.getenv("SELL_MONITOR_SMTP_PORT", "587")),
        username=os.getenv("SELL_MONITOR_SMTP_USERNAME", ""),
        password=os.getenv("SELL_MONITOR_SMTP_PASSWORD", ""),
        from_addr=from_addr,
        to_addr=to_addr,
        use_tls=_read_env_bool("SELL_MONITOR_SMTP_USE_TLS", True),
        subject_prefix=os.getenv("SELL_MONITOR_EMAIL_SUBJECT_PREFIX", "[SellMonitor]"),
    )


def _load_telegram_config() -> TelegramConfig | None:
    bot_token = os.getenv("SELL_MONITOR_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("SELL_MONITOR_TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        return None
    placeholder_tokens = {
        "your-bot-token",
        "<your-bot-token>",
        "bot_token_here",
    }
    placeholder_chat_ids = {
        "your-chat-id",
        "<your-chat-id>",
        "chat_id_here",
    }
    if bot_token.lower() in placeholder_tokens or chat_id.lower() in placeholder_chat_ids:
        return None
    return TelegramConfig(
        bot_token=bot_token,
        chat_id=chat_id,
        subject_prefix=os.getenv("SELL_MONITOR_TELEGRAM_SUBJECT_PREFIX", "[SellMonitor]"),
        api_base_url=os.getenv("SELL_MONITOR_TELEGRAM_API_BASE_URL", "https://api.telegram.org").strip(),
        proxy_url=_read_optional_proxy(
            "SELL_MONITOR_TELEGRAM_PROXY",
            "HTTPS_PROXY",
            "https_proxy",
            "HTTP_PROXY",
            "http_proxy",
        ),
    )


def _read_optional_proxy(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def _load_obsidian_monitor_config() -> ObsidianMonitorConfig | None:
    enabled = _read_env_bool("SELL_MONITOR_OBSIDIAN_MONITOR_ENABLED", True)
    if not enabled:
        return None
    monitor_dir = _read_path_env("SELL_MONITOR_OBSIDIAN_MONITOR_DIR", default=DEFAULT_OBSIDIAN_SELL_DIR)
    return ObsidianMonitorConfig(monitor_dir=monitor_dir)


def _load_obsidian_entry_config() -> ObsidianEntryConfig | None:
    enabled = _read_env_bool("SELL_MONITOR_OBSIDIAN_ENTRY_ENABLED", True)
    if not enabled:
        return None
    monitor_dir = _read_path_env("SELL_MONITOR_OBSIDIAN_ENTRY_DIR", default=DEFAULT_OBSIDIAN_ENTRY_DIR)
    return ObsidianEntryConfig(monitor_dir=monitor_dir)


def _load_miniqmt_config() -> MiniQmtConfig | None:
    userdata_path = os.getenv("SELL_MONITOR_MINIQMT_USERDATA_PATH")
    if not userdata_path:
        return None
    return MiniQmtConfig(userdata_path=Path(userdata_path))


def load_default_config(base_dir: Path | None = None) -> AppConfig:
    root = base_dir or Path(__file__).resolve().parents[1]
    _load_env_file(root)
    examples_dir = root / "examples"
    obsidian_monitor = _load_obsidian_monitor_config()
    obsidian_entry = _load_obsidian_entry_config()

    sell_watchlist_path = _read_path_env(
        "SELL_MONITOR_SELL_WATCHLIST_PATH",
        "SELL_MONITOR_WATCHLIST_PATH",
        "SELL_MONITOR_OBSIDIAN_WATCHLIST_PATH",
        default=DEFAULT_SELL_WATCHLIST_PATH,
    )
    entry_watchlist_path = _read_path_env(
        "SELL_MONITOR_ENTRY_WATCHLIST_PATH",
        default=DEFAULT_ENTRY_WATCHLIST_PATH,
    )
    positions_path = _read_path_env("SELL_MONITOR_POSITIONS_PATH", default=DEFAULT_OBSIDIAN_CONFIG_DIR / "positions.md")
    user_rules_path = _read_path_env("SELL_MONITOR_USER_RULES_PATH", default=DEFAULT_OBSIDIAN_CONFIG_DIR / "user_rules.md")
    market_data_path = _read_path_env("SELL_MONITOR_MARKET_DATA_PATH", default=examples_dir / "market_data.json")

    return AppConfig(
        base_dir=root,
        examples_dir=examples_dir,
        cache_dir=root / "runtime_cache",
        watchlist_path=sell_watchlist_path,
        sell_watchlist_path=sell_watchlist_path,
        entry_watchlist_path=entry_watchlist_path,
        positions_path=positions_path,
        user_rules_path=user_rules_path,
        market_data_path=market_data_path,
        provider=os.getenv("SELL_MONITOR_PROVIDER", "static").strip().lower(),
        email=_load_email_config(),
        telegram=_load_telegram_config(),
        obsidian_monitor=obsidian_monitor,
        obsidian_entry=obsidian_entry,
        miniqmt=_load_miniqmt_config(),
    )
