import os
import tempfile
import unittest

import numpy as np

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
        with parking_app._frame_lock:
            parking_app._latest_frame = None
            parking_app._latest_jpeg = None
        self.client = parking_app.app.test_client()

    def tearDown(self):
        tracking._TRACKING.clear()
        config.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    def test_local_dashboard_and_favicon(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Parking Local", response.data)
        self.assertIn(b"Reconocimiento de placas", response.data)
        favicon = self.client.get("/favicon.ico")
        self.assertEqual(favicon.status_code, 200)
        favicon.close()

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

    def test_frames_are_shared_in_memory_without_file_replacement(self):
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        parking_app._save_frame(frame)

        latest = parking_app._get_latest_frame()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.shape, frame.shape)
        self.assertIsNot(latest, frame)

        response = self.client.get("/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/jpeg")
        self.assertTrue(response.data.startswith(bytes([0xFF, 0xD8])))

    def test_unknown_plate_returns_404(self):
        self.assertEqual(self.client.get("/api/lookup/P1/UNKNOWN").status_code, 404)


if __name__ == "__main__":
    unittest.main()
