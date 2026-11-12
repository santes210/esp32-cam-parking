import unittest

import config
from core.alerts import Alerts


class AlertTests(unittest.TestCase):
    def test_demo_billing_alert_shows_mxn_and_respects_ttl(self):
        old_values = (
            config.SEND_FOR_REAL,
            config.TELEGRAM_CHAT_IDS,
            config.LOW_PRIORITY_TTL_MINUTES,
        )
        try:
            config.SEND_FOR_REAL = False
            config.TELEGRAM_CHAT_IDS = "12345"
            config.LOW_PRIORITY_TTL_MINUTES = 240
            alerts = Alerts()

            with self.assertLogs("core.alerts", level="INFO") as logs:
                alerts.send_low_priority(1, "P1", "ABC123", 12.5, 3.5)
                alerts.send_low_priority(1, "P1", "ABC123", 12.5, 3.5)

            messages = "\n".join(logs.output)
            self.assertIn("$12.50 MXN", messages)
            self.assertEqual(messages.count("Alerta de cobro"), 1)
        finally:
            (
                config.SEND_FOR_REAL,
                config.TELEGRAM_CHAT_IDS,
                config.LOW_PRIORITY_TTL_MINUTES,
            ) = old_values


if __name__ == "__main__":
    unittest.main()
