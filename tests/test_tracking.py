import os
import tempfile
import unittest
from datetime import datetime, timedelta

import config
from core import tracking


class TrackingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = config.DB_PATH
        config.DB_PATH = os.path.join(self.temp_dir.name, "parking.db")
        tracking._TRACKING.clear()
        tracking.init_lock()

    def tearDown(self):
        tracking._TRACKING.clear()
        config.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    def test_new_record_is_persisted_and_reloaded(self):
        original = tracking.add_record("abc123", "P1", 0.87)
        self.assertGreater(original.pk, 0)
        self.assertEqual(original.plaque, "ABC123")

        tracking._TRACKING.clear()
        tracking.init_lock()
        restored = tracking.find("P1", "ABC123")
        self.assertIsNotNone(restored)
        self.assertEqual(restored.pk, original.pk)
        self.assertAlmostEqual(restored.confidence, 0.87)

    def test_cost_is_mxn_and_rounds_up_partial_intervals(self):
        rec = tracking.add_record("ABC123", "P1", 0.9)
        rec.start = datetime.now() - timedelta(minutes=60)
        self.assertEqual(rec.cost, 0.0)

        rec.start = datetime.now() - timedelta(minutes=121)
        self.assertEqual(rec.cost, 2.0)

        rec.start = datetime.now() - timedelta(minutes=321)
        self.assertEqual(rec.cost, 4.0)
        self.assertEqual(config.format_mxn(rec.cost), "$4.00 MXN")

    def test_observation_updates_confidence_without_restarting_entry(self):
        rec = tracking.add_record("ABC123", "P1", 0.4)
        original_start = rec.start
        same = tracking.add_record("ABC123", "P1", 0.8)
        self.assertEqual(rec.pk, same.pk)
        self.assertEqual(same.start, original_start)
        self.assertEqual(same.confidence, 0.8)
        self.assertEqual(len(tracking.get_cars()), 1)

    def test_stale_vehicle_is_removed(self):
        rec = tracking.add_record("ABC123", "P1", 0.9)
        rec.detected_at = (datetime.now() - timedelta(minutes=10)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self.assertEqual(tracking.remove_stale(300), 1)
        self.assertIsNone(tracking.find("P1", "ABC123"))


if __name__ == "__main__":
    unittest.main()
