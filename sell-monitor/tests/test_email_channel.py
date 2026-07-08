from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from sell_monitor.config import EmailConfig
from sell_monitor.notifier.channels.email import EmailChannel


class EmailChannelTest(unittest.TestCase):
    def test_uses_starttls_for_plain_smtp(self) -> None:
        config = EmailConfig(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="user@example.com",
            password="pwd",
            from_addr="user@example.com",
            to_addr="to@example.com",
            use_ssl=False,
            use_tls=True,
        )
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp

        with patch("sell_monitor.notifier.channels.email.smtplib.SMTP", return_value=smtp):
            EmailChannel(config).send("subject", "message")

        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("user@example.com", "pwd")
        smtp.send_message.assert_called_once()

    def test_uses_smtp_ssl_when_enabled(self) -> None:
        config = EmailConfig(
            smtp_host="smtp.163.com",
            smtp_port=465,
            username="user@example.com",
            password="pwd",
            from_addr="user@example.com",
            to_addr="to@example.com",
            use_ssl=True,
            use_tls=False,
        )
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp

        with patch("sell_monitor.notifier.channels.email.smtplib.SMTP_SSL", return_value=smtp):
            EmailChannel(config).send("subject", "message")

        smtp.starttls.assert_not_called()
        smtp.login.assert_called_once_with("user@example.com", "pwd")
        smtp.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
