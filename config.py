"""Configuracion central del sistema de estacionamiento.

Todos los secretos y parametros de despliegue se pueden definir mediante
variables de entorno. Los valores predeterminados permiten ejecutar una demo
local sin credenciales ni servicios externos.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _int_env(name, default):
    return int(os.getenv(name, str(default)))


def _float_env(name, default):
    return float(os.getenv(name, str(default)))


# ---------------------------------------------------------------------------
# Cobro en pesos mexicanos
# ---------------------------------------------------------------------------
CURRENCY_CODE = "MXN"
CURRENCY_SYMBOL = "$"
GRACE_MINUTES = _int_env("GRACE_MINUTES", 120)
RATE_PER_INTERVAL_MINUTES = _int_env("RATE_PER_INTERVAL_MINUTES", 200)
RATE_PER_INTERVAL_MXN = _float_env("PARKING_RATE_MXN", 2.00)
ALERT_INTERVAL_MINUTES = _int_env("ALERT_INTERVAL_MINUTES", 120)
LOW_PRIORITY_TTL_MINUTES = _int_env("LOW_PRIORITY_TTL_MINUTES", 240)


def format_mxn(amount):
    """Devuelve un importe explicito en pesos mexicanos."""
    return f"{CURRENCY_SYMBOL}{amount:,.2f} {CURRENCY_CODE}"


# ---------------------------------------------------------------------------
# Zonas y persistencia
# ---------------------------------------------------------------------------
ZONES = [
    zone.strip()
    for zone in os.getenv("PARKING_ZONES", "P1,P2,P3").split(",")
    if zone.strip()
]
MONITOR_AREA = os.getenv("PARKING_MONITOR_AREA", ZONES[0])
DB_PATH = os.getenv("PARKING_DB", os.path.join(BASE_DIR, "data", "parking.db"))
VEHICLE_EXIT_TIMEOUT_SECONDS = _int_env("VEHICLE_EXIT_TIMEOUT_SECONDS", 300)


# ---------------------------------------------------------------------------
# Camara ESP32-CAM
# ---------------------------------------------------------------------------
ESP32_CAM_STREAM = os.getenv("ESP32_CAM_IP_STREAM", "http://192.168.1.64:81/stream")
CAM_FOLDER = os.path.join(BASE_DIR, "static")
CAM_STREAM_FILE = "monitor.jpg"
CAMERA_RECONNECT_SECONDS = _float_env("CAMERA_RECONNECT_SECONDS", 5)
CAMERA_HTTP_TIMEOUT_SECONDS = _float_env("CAMERA_HTTP_TIMEOUT_SECONDS", 10)
CAMERA_MAX_FRAME_BYTES = _int_env("CAMERA_MAX_FRAME_BYTES", 10_000_000)
RECOGNITION_INTERVAL_SECONDS = _float_env("RECOGNITION_INTERVAL_SECONDS", 2)


# ---------------------------------------------------------------------------
# Reconocimiento de placas
# ---------------------------------------------------------------------------
# demo          -> placa configurable, para probar el flujo sin ALPR.
# opencv        -> OpenCV + Tesseract OCR instalado en el equipo.
# openalpr      -> API OpenALPR Cloud; requiere ALPR_API_KEY.
# windows-local -> servicio HTTP local compatible con la respuesta OpenALPR.
RECOGNITION_BACKEND = os.getenv("RECOGNITION_BACKEND", "demo").lower()
DEMO_PLATE = os.getenv("DEMO_PLATE", "ABC123")
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")

ALPR_API_KEY = os.getenv("ALPR_API_KEY", "")
ALPR_CLOUD_URL = os.getenv(
    "ALPR_CLOUD_URL", "https://api.openalpr.com/v2/recognize_bytes"
)
ALPR_DAEMON_URL = os.getenv("ALPR_DAEMON_URL", "http://127.0.0.1:8000/data/detect")
ALPR_DEFAULT_REGION = os.getenv("ALPR_DEFAULT_REGION", "mx")
ALPR_REQUEST_TIMEOUT = _float_env("ALPR_REQUEST_TIMEOUT", 20)


# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------
SEND_FOR_REAL = os.getenv("SEND_FOR_REAL", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_DESTINATIONS = os.getenv("WHATSAPP_DESTINATIONS", "")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v22.0")
DISCORD_WEBHOOKS = os.getenv("DISCORD_WEBHOOKS", "")


def _split(text):
    return [part.strip() for part in text.split(",") if part.strip()]


def telegram_chat_ids():
    return _split(TELEGRAM_CHAT_IDS)


def whatsapp_destinations():
    return _split(WHATSAPP_DESTINATIONS)


def discord_webhooks():
    return [url.strip() for url in DISCORD_WEBHOOKS.splitlines() if url.strip()]


# ---------------------------------------------------------------------------
# Servidor HTTP
# ---------------------------------------------------------------------------
HOST = os.getenv("PARKING_HOST", "0.0.0.0")
PORT = _int_env("PORT", 5000)
