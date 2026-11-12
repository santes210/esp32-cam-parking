import itertools
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

import app as parking_app


class MJPEGHandler(BaseHTTPRequestHandler):
    jpeg = b""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        try:
            for _ in range(2):
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(self.jpeg)}\r\n\r\n".encode())
                self.wfile.write(self.jpeg + b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


class CameraTests(unittest.TestCase):
    def setUp(self):
        ok, encoded = cv2.imencode(".jpg", np.zeros((48, 64, 3), dtype=np.uint8))
        self.assertTrue(ok)
        MJPEGHandler.jpeg = encoded.tobytes()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), MJPEGHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_reads_individual_jpegs_from_mjpeg(self):
        url = f"http://127.0.0.1:{self.server.server_port}/stream"
        frames = parking_app._iter_mjpeg_frames(url)
        try:
            images = list(itertools.islice(frames, 2))
        finally:
            frames.close()
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0].shape, (48, 64, 3))


if __name__ == "__main__":
    unittest.main()
