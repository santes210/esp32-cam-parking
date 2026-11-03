"""Aplicación principal: captura del ESP32-CAM, reconocimiento de placas,
seguimiento de estacionamiento, cobro y alertas cada ALERT_INTERVAL_MINUTES."""

import logging
import os
import threading
import time

import cv2

import config
from core import alerts, recognizer, tracking

log = logging.getLogger("parking")


# ---------------------------------------------------------------------------
# Estado global
# ---------------------------------------------------------------------------
_cam_thread = None
_cam_lock = threading.Lock()
_recognizer = recognizer.build_recognizer()
_alerts = alerts.Alerts()


def _run_cam():
    """Lee el stream MJPEG de la ESP32-CAM y guarda cada frame en disco.

    En lugar de reconducir cuadros dentro del bucle, se escribe el archivo MJPEG
    completo y Flask sirve una vista fija vía ``send_file`` (más estable que el
    StreamingResponse del servidor).
    """
    import urllib.request

    url = config.ESP32_CAM_STREAM
    path = __import__("os").path.join(
        config.CAM_FOLDER, config.CAM_STREAM_FILE
    )
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = resp.read()
    with _cam_lock:
        with open(path, "wb") as f:
            f.write(data)
    log.info("Frame MJPEG recibido (%d bytes) -> %s", len(data), path)


def start_cam():
    global _cam_thread
    _cam_thread = threading.Thread(target=_run_cam, daemon=True)
    _cam_thread.start()


def get_cam_stream():
    """Devuelve la URL del MJPEG guardado (para servir con send_file)."""
    import os

    return os.path.join(config.CAM_FOLDER, config.CAM_STREAM_FILE)


def recognize_frame():
    """Lee un frame del MJPEG, lo reconoce su placa y registra el coche estacionado."""
    start = time.time()
    cam_file = get_cam_stream()
    if not os.path.exists(cam_file):
        log.warning("Sin frame disponible")
        return

    try:
        frame = cv2.imread(cam_file)
    except Exception as e:
        log.error("Error leyendo frame: %s", e)
        return

    if frame is None:
        log.error("No se pudo decodificar el frame")
        return

    plate = _recognizer.recognize(config.MONITOR_AREA)
    if plate is not None:
        rec = tracking.add_record(plate, config.MONITOR_AREA, confidence=0)
        _alerts.send_high_priority(
            rec.pk,
            rec.zone,
            rec.plaque,
            rec.confidence,
        )
        log.info("Reconocida: placa=%s zone=%s", plate, config.MONITOR_AREA)

    log.info("Reconocimiento en %.1fs ms", (time.time() - start) * 1000)


def recognize_loop():
    """Escanea el MJPEG cada ~1s. Se usa para 'darse' placas para las pruebas/veríf."."""
    tracking.init_lock()
    while True:
        try:
            recognize_frame()
        except Exception as e:
            log.error("Error en recognize_frame: %s", e)
        time.sleep(1)


def billing_loop():
    """Cada N minutos calcula el costo y lanza alertas de cobro (alta prioridad)."""
    while True:
        time.sleep(config.ALERT_INTERVAL_MINUTES)
        try:
            due = []
            for rec in tracking.get_cars():
                if rec.cost > 0:
                    due.append(rec)
                    _alerts.send_low_priority(
                        rec.pk,
                        rec.zone,
                        rec.plaque,
                        rec.cost,
                        rec.elapsed(),
                    )
            if not due:
                log.info("Ningún coche supera el umbral")
        except Exception as e:
            log.error("Error en billing_loop: %s", e)


# ---------------------------------------------------------------------------
# Flask: API + endpoints
# ---------------------------------------------------------------------------
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/live")
def live_cam():
    import os

    from flask import send_file

    path = os.path.join(config.CAM_FOLDER, config.CAM_STREAM_FILE)
    if not os.path.exists(path):
        return jsonify({"error": "sin frame"}), 503
    return send_file(path, mimetype="image/jpeg")


@app.route("/api/plates")
def api_plates():
    from core import tracking

    return jsonify([{"plate": r.plaque, "zone": r.zone} for r in tracking.get_cars()])


@app.route("/api/lookup/<zone>/<plate>")
def api_lookup(zone, plate):
    from core import tracking

    rec = tracking.find(zone, plate)
    if rec is None:
        return jsonify({"found": False, "zone": zone, "plate": plate})
    return jsonify(
        {
            "id": rec.pk,
            "zone": rec.zone,
            "plate": rec.plaque,
            "recognized_at": rec.recognized_at,
            "detected_at": rec.detected_at,
            "confidence": rec.confidence,
            "cost_usd": rec.cost,
            "elapsed_minutes": round(rec.elapsed(), 2),
            "needs_payment": rec.cost > 0,
        }
    )


@app.route("/api/stats")
def api_stats():
    from core import tracking

    if not tracking.get_cars():
        return jsonify({"total": 0})
    total, overs = 0, 0
    for r in tracking.get_cars():
        total += 1
        if r.cost > 0:
            overs += 1
    return jsonify({"total_parked": total, "needs_payment": overs})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Pointe de inicio
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    tracking.init_lock()
    start_cam()
    try:
        app.run(host="0.0.0.0", port=5000)
    finally:
        if _cam_thread is not None:
            _cam_thread.join()
