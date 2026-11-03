/*
 * ESP32-CAM - como emite la imagen de la zona de estacionamiento
 * --------------------------------------------------------------
 * La ESP32-CAM cuenta con un solo sensor de captura conectado DIRECTO a su
 * pantalla VGA (160x120). Por eso:
 *   - NO hay una camara "extra" que pueda ver la matricula y enviar un stream.
 *   - La unica forma que la ESP32-CAM ve el mundo ES lo que se muestra en su
 *     propio display (o lo que se le asigna por el pin de captura).
 *
 * PARA HACER ESTE PROYECTO Tienes 2 opciones de cableado:
 *
 *   OPCION A) ESP32-CAM emite MJPEG a otros dispositivos de la red
 *     - La ESP32-CAM se configura como SERVIDOR que transmite el MJPEG de su
 *       captura VGA y app.py consume ese stream.
 *     - Realear un modulo externo de captura conectado a la ESP32-CAM si
 *       quieres mayor flexibilidad de campo de vision / zoom.
 *
 *   OPCION B) ESP32-CAM como sensor local (OpenALPR en Raspberry Pi del servidor)
 *     - La ESP32-CAM se cablea como SERVIDOR (con un modulo camara externo OV2640)
 *       a la Raspberry Pi del servidor local, que corre OpenALPR.
 *
 * Referencias utiles de la comunidad (que ya mencionaste):
 *   - https://github.com/earledgunn/esp32cam-mjpeg-server
 *   - https://github.com/alec29/Octopus-OpenALPR
 *
 * Configuracion tipica de la ESP32-CAM (en ArduinoIDE -> Add WiFiStation):
 *   - SSID = "tu_red_wifi"
 *   - CONTRASENA = "tu_contrasena"
 *   - ESTACION IP = 192.168.1.64   (asi app.py consume:
 *                                              http://192.168.1.64:81/stream)
 */

#include <Arduino.h>
#include <WiFi.h>

/* ----------------------------- CONFIGURACION ---------------------------- */
const char* SSID = "INFINITUM6FE3";
const char* PASSWORD = "P7N3X4uKyQ";
const char* STATION_IP = "192.168.1.64";  // que ve el servidor local

void setup() {
    Serial.begin(115200);
    WiFi.begin(SSID, PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println();
    Serial.print("Conectado como SSID: ");
    Serial.println(SSID);
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());  // debe ser 192.168.1.64 para que funcione
}

void loop() {
    // Aqui va la logica de captura/stream de la camara (mjpeg / websocket).
    delay(2000);
}
