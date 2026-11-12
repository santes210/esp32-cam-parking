# Estacionamiento con ESP32-CAM — cobros en MXN

Proyecto Flask que recibe el video MJPEG de una ESP32-CAM, reconoce placas,
registra el tiempo de estacionamiento en SQLite y genera alertas con el importe
en **pesos mexicanos (MXN)**.

> El backend predeterminado es `opencv`: lee las placas de los frames recibidos
> por la ESP32-CAM mediante OpenCV + Tesseract OCR. Requiere Tesseract instalado
> en Windows. La precision depende de la iluminacion, el angulo y el enfoque.

## Componentes

- `static/esp32cam/esp32cam.ino`: firmware AI Thinker con OV2640 u OV3660.
- `app.py`: captura MJPEG, procesos de reconocimiento/cobro y API Flask.
- `core/recognizer.py`: backends demo, OpenCV/Tesseract y OpenALPR.
- `core/tracking.py`: entradas, ultima deteccion, persistencia y tarifas MXN.
- `core/alerts.py`: Telegram, WhatsApp Cloud API y Discord.

## Instalacion en Windows

Abre PowerShell dentro de la carpeta que contiene `app.py`. Si el ZIP creo dos
carpetas anidadas con el mismo nombre, entra en la carpeta interior:

```powershell
cd .\esp32-cam-parking-main\
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Instala tambien [Tesseract OCR para Windows](https://github.com/UB-Mannheim/tesseract/wiki)
en su ruta predeterminada (`C:\Program Files\Tesseract-OCR\tesseract.exe`). El paquete pip `pytesseract`
es solamente el conector; no incluye el programa OCR.

Configura la URL real que muestra el Monitor Serie de la ESP32-CAM:

```powershell
$env:ESP32_CAM_IP_STREAM = "http://192.168.1.64:81/stream"
python app.py
```

El panel local queda en `http://127.0.0.1:5000`. Los datos se crean en
`data/parking.db` y el ultimo frame se comparte en memoria, sin archivos temporales
ni bloqueos de `monitor.jpg` en Windows.

Para compilar la camara sigue la [guia de ESP32-CAM](static/esp32cam/README.md).

## Tarifa en pesos mexicanos

La configuracion predeterminada es:

| Parametro | Valor inicial | Significado |
| --- | ---: | --- |
| `GRACE_MINUTES` | 120 | Primeros 120 minutos sin cobro |
| `RATE_PER_INTERVAL_MINUTES` | 200 | Duracion de cada intervalo posterior |
| `PARKING_RATE_MXN` | 2.00 | Importe de cada intervalo: **$2.00 MXN** |
| `ALERT_INTERVAL_MINUTES` | 120 | Frecuencia de revision de cobros |
| `LOW_PRIORITY_TTL_MINUTES` | 240 | Espera minima entre alertas del mismo coche |

El valor de 2.00 es configurable y **no representa una conversion desde USD**.
Por ejemplo, para cobrar $20.00 MXN por cada intervalo de 60 minutos despues de
una hora gratis:

```powershell
$env:PARKING_RATE_MXN = "20.00"
$env:RATE_PER_INTERVAL_MINUTES = "60"
$env:GRACE_MINUTES = "60"
python app.py
```

Todo intervalo comenzado se cobra completo. Con la tarifa predeterminada, 121
minutos generan $2.00 MXN y 321 minutos generan $4.00 MXN.

## Reconocimiento de placas

Selecciona un backend con `RECOGNITION_BACKEND`.

### 1. OpenCV + Tesseract OCR (predeterminado)

Instala **Tesseract OCR** en Windows. La ruta predeterminada se detecta
automaticamente; si lo instalaste en otra carpeta, configura el ejecutable:

```powershell
$env:RECOGNITION_BACKEND = "opencv"
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
python app.py
```

El detector localiza posibles placas, mejora su contraste y ejecuta OCR por
lineas con una confianza minima. Ajusta distancia, enfoque e iluminacion para
mejorar la lectura. `OCR_MIN_CONFIDENCE` tiene un valor inicial de `0.35`.

### 2. OpenALPR Cloud

```powershell
$env:RECOGNITION_BACKEND = "openalpr"
$env:ALPR_API_KEY = "tu_api_key"
$env:ALPR_DEFAULT_REGION = "mx"
python app.py
```

### 3. Servicio OpenALPR local

Para un servicio HTTP que acepte un archivo multipart `image` y devuelva JSON con
`results[].plate` y `results[].confidence`:

```powershell
$env:RECOGNITION_BACKEND = "windows-local"
$env:ALPR_DAEMON_URL = "http://127.0.0.1:8000/data/detect"
python app.py
```

### Modo demo opcional

Solo para pruebas automatizadas o para comprobar cobros sin OCR, puedes seleccionar
una placa ficticia explícitamente:

```powershell
$env:RECOGNITION_BACKEND = "demo"
$env:DEMO_PLATE = "ABC123"
```

## Alertas opcionales

Por defecto `SEND_FOR_REAL=false`: los mensajes solo se escriben en la consola.
Para enviarlos, define `SEND_FOR_REAL=true` y las variables de uno de estos canales:

- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_IDS` (separados por comas).
- WhatsApp Cloud: `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`,
  `WHATSAPP_DESTINATIONS` (numeros separados por comas).
- Discord: `DISCORD_WEBHOOKS` (una URL por linea).

No guardes tokens reales en el codigo ni los subas a GitHub.

## Panel local y API

- `GET /`: panel local con iconos, video, estado, vehiculos e importes MXN.
- `GET /health`: estado, backend y antiguedad del ultimo frame.
- `GET /live`: ultimo frame JPEG.
- `GET /api/plates`: vehiculos, minutos e importe `cost_mxn`.
- `GET /api/lookup/<zona>/<placa>`: detalle, `formatted_cost` y moneda.
- `GET /api/stats`: total estacionado, vehiculos con cobro y total MXN.

Una placa deja de considerarse estacionada tras 300 segundos sin detecciones.
Cambia `VEHICLE_EXIT_TIMEOUT_SECONDS` segun la frecuencia y fiabilidad del ALPR.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Las pruebas usan bases SQLite temporales y no necesitan una camara fisica.
