from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sell_monitor.config import load_default_config
from sell_monitor.notifier.channels.email import EmailChannel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send a test email through the configured SMTP account.")
    parser.add_argument("--base-dir", type=Path, default=None, help="Project base directory.")
    parser.add_argument("--subject", type=str, default="[SellMonitor] 测试邮件", help="Email subject.")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_parser().parse_args()
    config = load_default_config(args.base_dir)
    if not config.email:
        print("未检测到邮件配置。请先在 sell-monitor-config.md 中补全 SMTP 参数。")
        return 1

    channel = EmailChannel(config.email)
    message = "\n".join(
        [
            "这是一封来自 sell-monitor 的测试邮件。",
            "",
            f"SMTP Host: {config.email.smtp_host}",
            f"SMTP Port: {config.email.smtp_port}",
            f"Use SSL: {'yes' if config.email.use_ssl else 'no'}",
            f"Use TLS: {'yes' if config.email.use_tls else 'no'}",
            f"From: {config.email.from_addr}",
            f"To: {config.email.to_addr}",
        ]
    )
    try:
        channel.send(args.subject, message)
    except Exception as exc:
        print(f"测试邮件发送失败: {exc}")
        return 1

    print(f"测试邮件已发送到 {config.email.to_addr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
