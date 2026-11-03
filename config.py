"""
Configuración central del sistema de parking.

TODO: correr TODO en Windows (sin Raspberry Pi). Los dos motores de reconocimiento
disponibles son:
  - "windows-local":  usa el DAEMON nativo de OpenALPR (servidor local "alprd") +
                      OpenCV local. NO requiere internet ni tarjeta de prueba.
  - "openalpr-api":   llama a la API CLOUD de OpenALPR (requiere cuenta de prueba).
  - "opencv":         detector local ligero de OpenCV (sin OpenALPR, pero sin
                      daemon). Útil si solo quieres la demo del flujo.
"""

import os


# ---------------------------------------------------------------------------
# Cobro por el tiempo de estacionamiento
# ---------------------------------------------------------------------------
GRACE_MINUTES = 120                                          # 2 horas gratis
RATE_PER_INTERVAL_MINUTES = 200                              # $2 USD por cada 200 min tras las 2h
ALERT_INTERVAL_MINUTES = 120                                 # cada 2 h -> alerta de "debe pagar"
LOW_PRIORITY_TTL_MINUTES = 240                               # ventana de silencio antes de re-alertar


# ---------------------------------------------------------------------------
# Zonas de estacionamiento vistas por la cámara / el daemon OpenALPR
# ---------------------------------------------------------------------------
ZONES = ["P1", "P2", "P3"]
MONITOR_AREA = "P1"


# ---------------------------------------------------------------------------
# Base de datos SQLite (persistencia; se guarda EN EL DISCO DE WINDOWS)
# ---------------------------------------------------------------------------
DB_PATH = os.getenv("PARKING_DB", os.path.join("data", "parking.db"))


# ---------------------------------------------------------------------------
# Streaming de la ESP32-CAM en Windows
# ---------------------------------------------------------------------------
# La ESP32 solo CAPTURA lo que ve y envía un stream por la red. El daemon OpenALPR
# (o OpenCV local, aquí mismo) es quien lee esas capturas y registra las placas.
ESP32_CAM_STREAM = os.getenv("ESP32_CAM_IP_STREAM", "http://192.168.1.64:81/stream")
CAM_FOLDER = "static"
CAM_STREAM_FILE = "monitor.mjpg"


# ---------------------------------------------------------------------------
# Alertas: Telegram / WhatsApp / Discord (en Windows)
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_DESTINATIONS = os.getenv("WHATSAPP_DESTINATIONS", "")
DISCORD_WEBHOOKS = os.getenv("DISCORD_WEBHOOKS", "")

send_real = os.getenv("SEND_FOR_REAL", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Motor de reconocimiento (Windows)
# ---------------------------------------------------------------------------
RECOGNITION_BACKEND = os.getenv("RECOGNITION_BACKEND", "windows-local")

# --- OpenALPR: comunicarse con el DAEMON (alprd) que corre EN WINDOWS ---
# NO es la API CLOUD. El daemon "alprd" ejecuta el modelo offline (modelo-3)
# y responde por HTTP local sin internet.
ALPR_DAEMON_URL = os.getenv("ALPR_DAEMON_URL", "http://127.0.0.1:8000/data/detect")  # daemon alprd en Windows
ALPR_DEFAULT_REGIONS = os.getenv("ALPR_DEFAULT_REGIONS", "us,eu").split(",")            # regiones del DAEMON

# --- Cliente HTTP para el daemon (opcional; se usa por defecto) ---
ALPR_CLIENT_TIMEOUT = 20
ALPR_REQUEST_TIMEOUT = 15

# --- Switch de envió vs consola ---
SEND_FOR_REAL = send_real


# ---------------------------------------------------------------------------
# Helpers de lectura de parametros (usados por Alerts); deben devolver listas
# sin elementos vacios.
# ---------------------------------------------------------------------------
def _split(text):
    """Devuelve una lista sin elementos vacios de `text` (separa por virgulas)."""
    if not text:
        return []
    return [p.strip() for p in text.split(",") if p.strip()]


def telegram_chat_ids():
    """Devuelve la lista de IDs de chat de Telegram (sin vacios)."""
    return _split(TELEGRAM_CHAT_IDS)


def whatsapp_destinations():
    """Devuelve la lista de destinatarios de WhatsApp (sin vacios)."""
    return _split(WHATSAPP_DESTINATIONS)


def discord_webhooks():
    """Devuelve la lista de Webhooks JSON de Discord (sin vacios)."""
    return [x.strip() for x in DISCORD_WEBHOOKS.splitlines() if x.strip()]
