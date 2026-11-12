"""Aplicacion Flask: captura ESP32-CAM, ALPR, seguimiento, cobros y alertas."""

import logging
import threading
import time
import urllib.request

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template

import config
from core import alerts, recognizer, tracking

log = logging.getLogger("parking")

_cam_thread = None
_cam_last_frame_at = 0.0
_frame_lock = threading.Lock()
_latest_frame = None
_latest_jpeg = None
_recognizer = recognizer.build_recognizer()
_alerts = alerts.Alerts()
app = Flask(__name__)


# ---------------------------------------------------------------------------
# Captura de camara
# ---------------------------------------------------------------------------
def _save_frame(frame):
    """Comparte el ultimo frame en memoria sin bloqueos de archivos en Windows."""
    global _cam_last_frame_at, _latest_frame, _latest_jpeg
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("No se pudo codificar el frame de la camara")

    with _frame_lock:
        _latest_frame = frame.copy()
        _latest_jpeg = encoded.tobytes()
        _cam_last_frame_at = time.time()


def _get_latest_frame():
    with _frame_lock:
        return None if _latest_frame is None else _latest_frame.copy()


def _get_latest_jpeg():
    with _frame_lock:
        return _latest_jpeg


def _read_exact(response, length):
    """Lee exactamente un JPEG, incluso si el socket entrega partes pequenas."""
    chunks = []
    remaining = length
    while remaining:
        chunk = response.read(remaining)
        if not chunk:
            raise ConnectionError("El stream termino en medio de un frame JPEG")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _seek_boundary(response, delimiter):
    while True:
        line = response.readline(65536)
        if not line:
            return False
        stripped = line.strip()
        if stripped == delimiter:
            return True
        if stripped == delimiter + b"--":
            return False


def _iter_mjpeg_frames(url):
    """Genera frames desde MJPEG con Content-Length o desde un JPEG individual."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=config.CAMERA_HTTP_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get_content_type()
        if content_type == "image/jpeg":
            data = response.read(config.CAMERA_MAX_FRAME_BYTES + 1)
            if len(data) > config.CAMERA_MAX_FRAME_BYTES:
                raise ValueError("El JPEG excede CAMERA_MAX_FRAME_BYTES")
            yield cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            return
        if content_type != "multipart/x-mixed-replace":
            raise ValueError(f"La camara devolvio un tipo no soportado: {content_type}")

        boundary = response.headers.get_param("boundary", "frame")
        if isinstance(boundary, tuple):
            boundary = boundary[0]
        delimiter = boundary.encode("ascii")
        if not delimiter.startswith(b"--"):
            delimiter = b"--" + delimiter

        if not _seek_boundary(response, delimiter):
            return
        while True:
            headers = {}
            while True:
                line = response.readline(65536)
                if not line:
                    return
                if line in {b"\r\n", b"\n"}:
                    break
                name, separator, value = line.decode("latin-1").partition(":")
                if separator:
                    headers[name.strip().lower()] = value.strip()

            length = int(headers.get("content-length", "0"))
            if length <= 0 or length > config.CAMERA_MAX_FRAME_BYTES:
                raise ValueError(
                    "Cada parte MJPEG debe incluir un Content-Length valido y menor "
                    "que CAMERA_MAX_FRAME_BYTES"
                )
            data = _read_exact(response, length)
            frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                yield frame
            if not _seek_boundary(response, delimiter):
                return


def _run_cam():
    """Lee continuamente MJPEG y reconecta si la camara se desconecta."""
    global _cam_last_frame_at
    while True:
        try:
            log.info("Conectando con la camara: %s", config.ESP32_CAM_STREAM)
            for frame in _iter_mjpeg_frames(config.ESP32_CAM_STREAM):
                _save_frame(frame)
            log.warning("El stream de la camara termino")
        except Exception:
            log.exception("Error leyendo la camara")

        _cam_last_frame_at = 0.0
        time.sleep(config.CAMERA_RECONNECT_SECONDS)


def start_cam():
    global _cam_thread
    if _cam_thread is not None and _cam_thread.is_alive():
        return
    _cam_thread = threading.Thread(target=_run_cam, name="camera", daemon=True)
    _cam_thread.start()


# ---------------------------------------------------------------------------
# Reconocimiento y cobro
# ---------------------------------------------------------------------------
def recognize_frame():
    """Reconoce el ultimo frame recibido por la camara."""
    frame = _get_latest_frame()
    if frame is None:
        return None

    result = _recognizer.recognize(frame)
    if result is None:
        return None

    is_new = tracking.find(config.MONITOR_AREA, result.plate) is None
    rec = tracking.add_record(result.plate, config.MONITOR_AREA, result.confidence)
    if is_new:
        _alerts.send_high_priority(rec.pk, rec.zone, rec.plaque, rec.confidence)
        log.info("Nueva placa=%s zona=%s", rec.plaque, rec.zone)
    return rec


def recognize_loop():
    while True:
        try:
            recognize_frame()
            removed = tracking.remove_stale()
            if removed:
                log.info("Vehiculos retirados por ausencia: %d", removed)
        except Exception:
            log.exception("Error en el ciclo de reconocimiento")
        time.sleep(config.RECOGNITION_INTERVAL_SECONDS)


def billing_loop():
    while True:
        time.sleep(config.ALERT_INTERVAL_MINUTES * 60)
        try:
            for rec in tracking.get_cars():
                if rec.cost > 0:
                    _alerts.send_low_priority(
                        rec.pk,
                        rec.zone,
                        rec.plaque,
                        rec.cost,
                        rec.elapsed_minutes / 60.0,
                    )
        except Exception:
            log.exception("Error en el ciclo de cobro")


def start_workers():
    tracking.init_lock()
    start_cam()
    threading.Thread(target=recognize_loop, name="recognition", daemon=True).start()
    threading.Thread(target=billing_loop, name="billing", daemon=True).start()


# ---------------------------------------------------------------------------
# Panel local y API HTTP
# ---------------------------------------------------------------------------
@app.route("/")
def dashboard():
    return render_template("index.html", monitor_area=config.MONITOR_AREA)


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.svg")


@app.route("/live")
def live_cam():
    jpeg = _get_latest_jpeg()
    if jpeg is None:
        return jsonify({"error": "Sin frame disponible"}), 503
    return Response(
        jpeg,
        mimetype="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@app.route("/api/plates")
def api_plates():
    return jsonify(
        [
            {
                "id": rec.pk,
                "plate": rec.plaque,
                "zone": rec.zone,
                "confidence": rec.confidence,
                "elapsed_minutes": round(rec.elapsed_minutes, 2),
                "cost_mxn": rec.cost,
            }
            for rec in tracking.get_cars()
        ]
    )


@app.route("/api/lookup/<zone>/<plate>")
def api_lookup(zone, plate):
    rec = tracking.find(zone, plate)
    if rec is None:
        return jsonify({"found": False, "zone": zone, "plate": plate}), 404

    return jsonify(
        {
            "found": True,
            "id": rec.pk,
            "zone": rec.zone,
            "plate": rec.plaque,
            "recognized_at": rec.recognized_at,
            "detected_at": rec.detected_at,
            "confidence": rec.confidence,
            "cost_mxn": rec.cost,
            "formatted_cost": config.format_mxn(rec.cost),
            "currency": config.CURRENCY_CODE,
            "elapsed_minutes": round(rec.elapsed_minutes, 2),
            "needs_payment": rec.cost > 0,
        }
    )


@app.route("/api/stats")
def api_stats():
    cars = tracking.get_cars()
    return jsonify(
        {
            "total_parked": len(cars),
            "needs_payment": sum(rec.cost > 0 for rec in cars),
            "total_cost_mxn": round(sum(rec.cost for rec in cars), 2),
            "currency": config.CURRENCY_CODE,
        }
    )


@app.route("/health")
def health():
    frame_age = time.time() - _cam_last_frame_at if _cam_last_frame_at else None
    return jsonify(
        {
            "status": "ok",
            "recognition_backend": config.RECOGNITION_BACKEND,
            "currency": config.CURRENCY_CODE,
            "last_frame_age_seconds": round(frame_age, 2)
            if frame_age is not None
            else None,
        }
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    start_workers()
    log.info("Servidor disponible en http://127.0.0.1:%d", config.PORT)
    app.run(host=config.HOST, port=config.PORT)
