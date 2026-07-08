from __future__ import annotations

import smtplib
from email.message import EmailMessage

from sell_monitor.config import EmailConfig


class EmailChannel:
    def __init__(self, config: EmailConfig) -> None:
        self.config = config

    def send(self, subject: str, message: str) -> None:
        if not self.config.from_addr or not self.config.to_addr:
            raise RuntimeError("Email channel requires both SELL_MONITOR_EMAIL_FROM and SELL_MONITOR_EMAIL_TO.")

        email = EmailMessage()
        email["From"] = self.config.from_addr
        email["To"] = self.config.to_addr
        email["Subject"] = subject
        email.set_content(message)

        smtp_cls = smtplib.SMTP_SSL if self.config.use_ssl else smtplib.SMTP
        with smtp_cls(self.config.smtp_host, self.config.smtp_port, timeout=20) as smtp:
            if self.config.use_tls and not self.config.use_ssl:
                smtp.starttls()
            if self.config.username:
                smtp.login(self.config.username, self.config.password)
            smtp.send_message(email)
