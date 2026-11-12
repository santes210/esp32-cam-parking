# AI Thinker ESP32-CAM: compilación y flasheo

El archivo `esp32cam.ino` detecta automáticamente los sensores **OV2640 y OV3660**
y publica:

- `http://<IP>/capture`: una captura JPEG.
- `http://<IP>:81/stream`: video MJPEG.
- `http://<IP>/`: página de estado.

### Uso con OV3660

No hay que cambiar los pines si el OV3660 está instalado en el mismo módulo AI
Thinker: comparte la conexión del flex y el driver lo identifica mediante SCCB.
Al iniciar, el Monitor Serie mostrará `Camara OV3660 detectada`.

El firmware comienza en `FRAMESIZE_VGA` (640 × 480) para que el MJPEG sea fluido.
Para aprovechar la mayor resolución del OV3660, cambia `CAMERA_FRAME_SIZE` a
`FRAMESIZE_SVGA` (800 × 600) o `FRAMESIZE_UXGA` (1600 × 1200). Para UXGA se
recomienda PSRAM; una resolución mayor aumenta el consumo de memoria, el ancho de
banda y el tiempo entre cuadros. Empieza probando `/capture` antes de `/stream`.
El OV3660 admite hasta QXGA, pero no se recomienda para video continuo en esta
aplicación.

Si usas una placa ESP32-CAM distinta de AI Thinker, sí debes sustituir la tabla de
pines por la del fabricante. Seleccionar otro modelo de sensor en Arduino no es
necesario: solo se selecciona la placa.

## 1. Preparar Arduino IDE

1. Abre **Archivo > Preferencias** y, si todavía no está, agrega esta URL en
   **Gestor de URLs adicionales de tarjetas**:

   ```text
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```

2. En **Herramientas > Placa > Gestor de tarjetas**, instala
   **esp32 by Espressif Systems**. Si la instalación anterior quedó incompleta,
   desinstálala y vuelve a instalarla antes de compilar.
3. Selecciona **Herramientas > Placa > esp32 > AI Thinker ESP32-CAM**.
4. Usa estas opciones:
   - **Upload Speed:** `115200` (reduce problemas con adaptadores USB-UART).
   - **Flash Frequency:** `40MHz` si el valor predeterminado falla.
   - **Partition Scheme:** `Default 4MB with spiffs` o `Huge APP`.
   - **PSRAM:** `Enabled` si la opción está disponible.
   - **Port:** el puerto COM del adaptador USB-UART.
5. Abre `esp32cam.ino` y sustituye `TU_SSID` y `TU_PASSWORD` por los datos de
   una red WiFi **de 2.4 GHz**. El ESP32-CAM no se conecta a redes solo 5 GHz.

El sketch usa solamente `Arduino.h`, `WiFi.h` y `esp_camera.h`, incluidos con el
paquete de Espressif. No hay que instalar una librería ESP32-CAM independiente.

> Si Arduino se queda mucho tiempo en una instalación o compilación inicial,
> revisa primero la salida completa. Una instalación dañada del paquete ESP32,
> antivirus o OneDrive bloqueando la carpeta de Arduino pueden causarlo; no es
> lo mismo que el error de conexión de `esptool` mostrado al final de la carga.

## 2. Cableado para cargar el programa

La AI Thinker ESP32-CAM **no tiene puerto USB**. Hace falta un adaptador
USB-UART (FTDI, CP2102 o CH340) con señales de **3.3 V**.

| ESP32-CAM | Adaptador USB-UART |
| --- | --- |
| `5V` | `5V` |
| `GND` | `GND` |
| `U0R` (RX) | `TX` |
| `U0T` (TX) | `RX` |
| `IO0` | `GND` solamente durante la carga |

- Cruza TX/RX: **TX con U0R y RX con U0T**.
- Alimenta por `5V` con una fuente estable capaz de entregar al menos 500 mA;
  se recomienda 1 A para evitar reinicios. No alimentes la placa desde el pin
  de 3.3 V de un adaptador USB-UART pequeño.
- Aunque la alimentación sea de 5 V, las señales TX/RX deben ser de 3.3 V.
- Conecta firmemente el flex de la cámara y desconecta otros periféricos durante
  las pruebas. Si usas una fuente externa, une su GND con el GND del adaptador.

## 3. Cargar el sketch

1. Cierra el **Monitor Serie** y cualquier otra ventana de Arduino u otro
   programa que pueda estar usando el puerto COM.
2. Confirma en el Administrador de dispositivos que el puerto seleccionado es el
   del adaptador. Instala su driver CH340/CP2102/FTDI si el puerto no aparece.
3. Con `IO0` unido a `GND`, pulsa y suelta `RESET` en la ESP32-CAM.
4. Pulsa **Subir**. Cuando aparezca `Connecting...`, vuelve a pulsar `RESET` si
   no comienza la carga. No mantengas pulsado RESET durante toda la operación.
5. Al terminar, **quita el puente `IO0`-`GND`** y pulsa `RESET` otra vez. Si IO0
   queda a GND, la placa no ejecutará normalmente el sketch.
6. Abre el Monitor Serie a `115200` baudios. Debe mostrar la IP y las URLs de
   captura y stream.

### Error `Failed to connect to ESP32: Serial data stream stopped`

Ese error ocurre en la comunicación USB-UART, **antes de ejecutar el nuevo
sketch**. Cambiar el código no lo corrige. Prueba, en este orden:

1. Verifica el puente `IO0`-`GND` y pulsa RESET antes de `Connecting...`.
2. Comprueba que TX/RX están cruzados y que GND es común.
3. Usa un cable USB **de datos**, corto y en buen estado; prueba otro puerto USB.
4. Usa una fuente de 5 V suficiente. Una caída de alimentación puede detener el
   flujo serie a mitad del intento.
5. Selecciona `115200` como Upload Speed y cierra otros monitores serie.
6. Prueba otro adaptador USB-UART si el error continúa.

## 4. Comprobar el funcionamiento

Con la IP mostrada por el Monitor Serie, abre primero:

```text
http://<IP>/capture
```

Después prueba el stream en VLC (**Medio > Abrir ubicación de red**) o desde el
backend:

```text
http://<IP>:81/stream
```

Si usas DHCP (configuración predeterminada), ajusta `ESP32_CAM_IP_STREAM` en el
backend con la IP real. Para fijar `192.168.1.64`, activa `USE_STATIC_IP` en el
sketch y asegúrate de que `GATEWAY`, `SUBNET` y el rango de IP correspondan a tu
router. No uses una IP que el router ya haya asignado a otro equipo.

### Errores frecuentes al iniciar

- `E ... camera probe failed` / error `0x105`: revisa el flex y su orientación,
  confirma que la placa seleccionada sea **AI Thinker ESP32-CAM** y actualiza el
  paquete `esp32 by Espressif Systems` si está muy desactualizado. Este error
  indica que no se detectó el sensor; todavía no distingue entre OV2640 y OV3660.
- Brownout detector / reinicios: mejora la alimentación de 5 V y el cableado.
- Se agota el tiempo WiFi: verifica credenciales y usa una red de 2.4 GHz.
- La imagen no abre: quita `IO0`-`GND`, pulsa RESET y consulta el Monitor Serie.
