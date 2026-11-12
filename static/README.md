# Estacionamiento Automatizado: ESP32-CAM + OpenCV/OpenALPR

Sistema que lee la **matrícula** de los vehículos con una **ESP32-CAM** y un
backend potente (Windows en la demo, Raspberry Pi para producción), calcula
**cuánto tiempo** está cada vehículo estacionado en una zona y envía
**alertas de cobro** cada 2 horas por **Telegram / WhatsApp / Discord**.

| Componente | Responsabilidad | Qué corre |
| --- | --- | --- |
| ESP32-CAM | Captura la imagen de la matrícula y la transmite por la red | Solo captura y stream MJPEG (`static/esp32cam/esp32cam.ino`) |
| Backend Windows / Raspberry Pi | Reconoce la matrícula, calcula el costo y envía alertas | `config.py`, `core/*.py`, `app.py` |
| SQLite | Estado del sistema (registro de cada vehículo por placa/`zona`) | `db_schema.sql`, `core/tracking.py` |

## Requerimientos previos

### Windows (modo de demostración)
- Python 3.10+ (64 bits)
- `pip install -r requirements.txt` (incluye **OpenCV**)
- Un ESP32-CAM con firmware que emita el stream MJPEG (`static/esp32cam/esp32cam.ino`)
- El firmware debe estar en `http://<IP>:81/stream` de la red local.
- La [guía de compilación y flasheo](esp32cam/README.md) incluye el cableado
  USB-UART y la solución para `Failed to connect to ESP32`.

### Raspberry Pi (producción recomendada)
- Raspberry Pi + `picamera` (OpenALPR requiere `torch` y un modelo de 3 GB RAM).
- Se usa el backend `openalpr` para máxima precisión. (`RECOGNITION_BACKEND=openalpr`)

## Estructura

```
agent/
├── config.py               # Umbrales de cobro, zonas y parámetros (2h gratis, cadencia, envios, alertas)
├── static/esp32cam/         # Firmware MJPEG y guía de compilación/flasheo
├── core/
│   ├── recognicer.py        # Reconocimiento: OpenCV (Windows) vs OpenALPR (Pi)
│   ├── tracking.py          # Persistencia de records y tracking de tiempo/costo
│   └── alerts.py            # Alertas Telegram/WhatsApp/Discord + l6gica de cobro
├── db_schema.sql            # DDL de la base de datos
├── requirements.txt
└── app.py                   # Flask: captura del stream, API + loops de billing/alertas
```

## Parámetros de cobro y alertas

| Concepto | Umbral (config.py) | Detalle |
| --- | --- | --- |
| Gratuidad (`GRACE_MINUTES`) | **120 min** (2h gratis) |
| Cobro por intervalo | **200 min / $2** + $x por exceso |
| Alerta de cobro (`ALERT_INTERVAL_MINUTES`) | **120 min** (cada 2h) |
| TTL de alerta (`LOW_PRIORITY_TTL_MINUTES`) | **240 min** |

## Como usar (Windows)

```bash
pip install -r requirements.txt
```

Configura `config.py`: IP de la ESP32-CAM, zonas y canales de alerta.

Ejecuta:

```bash
python app.py    # escanea el stream, calcula costo y envia alertas
```

Endpoints HTTP en `http://<IP>:5000`:

- `/live`      stream MJPEG de la cámara
- `/api/plates` listado de vehículos estacionados
- `/api/lookup/<zone>/<plate>` detalle de costo/duracion de un coche
- `/api/stats`  estadisticas de park.

## Backends de reconocimiento

- `RECOGNITION_BACKEND=opencv` (default, Windows): detector local ligero, devolviendo un detector demo determinista.
- `RECOGNITION_BACKEND=openalpr` (Pi): llama a la API OpenALPR para máxima precisión (requiere tarjeta de prueba + internet).

## Notas importantes

1. **La ESP32-CAM no debe "pensar" la deteccion**: es limitada en memoria/RAM; la captura y el stream van separados del backend.
2. En la demo de Windows todo corre localmente (`SEND_FOR_REAL=false`, envios solo en consola).
3. Para producción se recomienda la Raspberry Pi con OpenALPR para mayor precisión, pero funciona con el backend de Windows.
