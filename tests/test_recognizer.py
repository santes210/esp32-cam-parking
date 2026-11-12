import unittest
from unittest.mock import patch

import numpy as np

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

    def test_opencv_is_default_real_recognition_backend(self):
        self.assertEqual(config.RECOGNITION_BACKEND, "opencv")
        self.assertIsInstance(
            recognizer.build_recognizer(), recognizer.OpenCVRecognizer
        )

    def test_extracts_real_plate_text_without_labels(self):
        self.assertEqual(
            recognizer.OpenCVRecognizer._plates_in_text("PLACA ABC-123"),
            ["ABC123"],
        )
        self.assertIn(
            "ABC1234",
            recognizer.OpenCVRecognizer._plates_in_text("ABC 12 34"),
        )

    def test_ocr_lines_generate_confident_plate_candidates(self):
        engine = recognizer.OpenCVRecognizer()
        ocr_data = {
            "text": ["PLACA", "ABC-123"],
            "conf": ["95", "90"],
            "block_num": [1, 1],
            "par_num": [1, 1],
            "line_num": [1, 1],
        }
        image = np.zeros((40, 120), dtype=np.uint8)
        with patch.object(engine._pytesseract, "image_to_data", return_value=ocr_data):
            candidates = engine._ocr_candidates(image, 7)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].plate, "ABC123")
        self.assertAlmostEqual(candidates[0].confidence, 0.925)

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
