import unittest

import config
from core import recognizer


class RecognizerTests(unittest.TestCase):
    def test_demo_backend_returns_normalized_plate(self):
        old_plate = config.DEMO_PLATE
        try:
            config.DEMO_PLATE = "abc-123"
            result = recognizer.DemoRecognizer().recognize(object())
            self.assertEqual(result.plate, "ABC123")
            self.assertEqual(result.confidence, 0.99)
        finally:
            config.DEMO_PLATE = old_plate

    def test_openalpr_response_uses_best_valid_candidate(self):
        result = recognizer.OpenALPRRecognizer._from_payload(
            {
                "results": [
                    {"plate": "bad", "confidence": 99},
                    {"plate": "abc-123", "confidence": 87.5},
                    {"plate": "XYZ-987", "confidence": 60},
                ]
            }
        )
        self.assertEqual(result.plate, "ABC123")
        self.assertAlmostEqual(result.confidence, 0.875)

    def test_openalpr_response_can_be_empty(self):
        self.assertIsNone(recognizer.OpenALPRRecognizer._from_payload({"results": []}))


if __name__ == "__main__":
    unittest.main()
