import os
import tempfile
import unittest

import app as parking_app
import config
from core import tracking


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = config.DB_PATH
        config.DB_PATH = os.path.join(self.temp_dir.name, "parking.db")
        tracking._TRACKING.clear()
        tracking.init_lock()
        self.client = parking_app.app.test_client()

    def tearDown(self):
        tracking._TRACKING.clear()
        config.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["currency"], "MXN")

    def test_lookup_and_stats_use_mxn(self):
        tracking.add_record("ABC123", "P1", 0.9)
        response = self.client.get("/api/lookup/P1/ABC123")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["found"])
        self.assertEqual(payload["cost_mxn"], 0.0)
        self.assertEqual(payload["currency"], "MXN")
        self.assertNotIn("cost_usd", payload)

        stats = self.client.get("/api/stats").get_json()
        self.assertEqual(stats["total_parked"], 1)
        self.assertEqual(stats["currency"], "MXN")

    def test_unknown_plate_returns_404(self):
        self.assertEqual(self.client.get("/api/lookup/P1/UNKNOWN").status_code, 404)


if __name__ == "__main__":
    unittest.main()
