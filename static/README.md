# Recursos de la ESP32-CAM

- `esp32cam/esp32cam.ino`: firmware para AI Thinker ESP32-CAM con OV2640 u OV3660.
- `esp32cam/README.md`: instalacion del paquete ESP32, cableado USB-UART,
  flasheo y resolucion de errores.
El backend publica:

- `http://<IP>/capture`: captura JPEG individual.
- `http://<IP>:81/stream`: stream MJPEG consumido por `app.py`.

Para instalar y ejecutar todo el proyecto, configurar el reconocimiento y cambiar
la tarifa en pesos mexicanos, consulta el [README principal](../README.md).
