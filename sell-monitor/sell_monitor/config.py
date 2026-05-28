from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
class ObsidianMonitorConfig:
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
    positions_path: Path
    user_rules_path: Path
    market_data_path: Path
    provider: str
    email: EmailConfig | None
    obsidian_monitor: ObsidianMonitorConfig | None
    miniqmt: MiniQmtConfig | None


def _load_env_file(root: Path) -> None:
    env_path = Path(os.getenv("SELL_MONITOR_ENV_FILE", root / ".env"))
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
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


def _load_obsidian_monitor_config() -> ObsidianMonitorConfig | None:
    enabled = _read_env_bool("SELL_MONITOR_OBSIDIAN_MONITOR_ENABLED", True)
    if not enabled:
        return None
    monitor_dir = os.getenv(
        "SELL_MONITOR_OBSIDIAN_MONITOR_DIR",
        r"E:\tools\OB\Obsidian\Trade\notes\monitor",
    ).strip()
    if not monitor_dir:
        return None
    return ObsidianMonitorConfig(monitor_dir=Path(monitor_dir))


def _load_miniqmt_config() -> MiniQmtConfig | None:
    userdata_path = os.getenv("SELL_MONITOR_MINIQMT_USERDATA_PATH")
    if not userdata_path:
        return None
    return MiniQmtConfig(userdata_path=Path(userdata_path))


def load_default_config(base_dir: Path | None = None) -> AppConfig:
    root = base_dir or Path(__file__).resolve().parents[1]
    _load_env_file(root)
    examples_dir = root / "examples"
    return AppConfig(
        base_dir=root,
        examples_dir=examples_dir,
        cache_dir=root / "runtime_cache",
        watchlist_path=examples_dir / "watchlist.json",
        positions_path=examples_dir / "positions.json",
        user_rules_path=examples_dir / "user_rules.json",
        market_data_path=examples_dir / "market_data.json",
        provider=os.getenv("SELL_MONITOR_PROVIDER", "static").strip().lower(),
        email=_load_email_config(),
        obsidian_monitor=_load_obsidian_monitor_config(),
        miniqmt=_load_miniqmt_config(),
    )
