/*
 * Firmware para AI Thinker ESP32-CAM (OV2640).
 *
 * Endpoints:
 *   http://<IP>/          Estado del dispositivo
 *   http://<IP>/capture   Una imagen JPEG
 *   http://<IP>:81/stream Stream MJPEG para app.py
 *
 * Probado con las API incluidas en el paquete "esp32 by Espressif Systems".
 * No requiere librerias Arduino adicionales.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_camera.h>

/* ----------------------------- CONFIGURACION ---------------------------- */

// Cambia estos dos valores por los de tu red WiFi de 2.4 GHz.
const char *WIFI_SSID = "TU_SSID";
const char *WIFI_PASSWORD = "TU_PASSWORD";

// DHCP es la opcion mas sencilla: la IP asignada aparece en el monitor serie.
// Si se necesita 192.168.1.64, cambia a true y revisa tambien puerta de enlace.
const bool USE_STATIC_IP = false;
const IPAddress STATIC_IP(192, 168, 1, 64);
const IPAddress GATEWAY(192, 168, 1, 254);
const IPAddress SUBNET(255, 255, 255, 0);
const IPAddress DNS(8, 8, 8, 8);

const uint32_t WIFI_TIMEOUT_MS = 30000;
const uint16_t HTTP_PORT = 80;
const uint16_t STREAM_PORT = 81;

// Pines de la camara en la placa AI Thinker ESP32-CAM.
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

WiFiServer httpServer(HTTP_PORT);
WiFiServer streamServer(STREAM_PORT);

bool initCamera() {
    camera_config_t config = {};
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_VGA;  // 640 x 480
    config.jpeg_quality = 12;           // Menor numero = mejor calidad.
    config.fb_count = 1;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
    config.fb_location = CAMERA_FB_IN_DRAM;

    if (psramFound()) {
        config.fb_count = 2;
        config.grab_mode = CAMERA_GRAB_LATEST;
        config.fb_location = CAMERA_FB_IN_PSRAM;
    }

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("Error al inicializar la camara: 0x%x\n", err);
        return false;
    }

    sensor_t *sensor = esp_camera_sensor_get();
    if (sensor == nullptr) {
        Serial.println("No se pudo obtener el sensor de la camara");
        esp_camera_deinit();
        return false;
    }

    // Ajusta estas orientaciones si la imagen aparece invertida.
    sensor->set_vflip(sensor, 0);
    sensor->set_hmirror(sensor, 0);
    sensor->set_brightness(sensor, 1);
    sensor->set_saturation(sensor, -1);

    Serial.printf("Camara lista. PSRAM: %s\n", psramFound() ? "si" : "no");
    return true;
}

bool connectWiFi() {
    if (USE_STATIC_IP && !WiFi.config(STATIC_IP, GATEWAY, SUBNET, DNS)) {
        Serial.println("No se pudo configurar la IP estatica");
        return false;
    }

    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);  // Evita interrupciones del stream por ahorro de energia.
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    Serial.printf("Conectando a WiFi %s", WIFI_SSID);
    const uint32_t startedAt = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - startedAt >= WIFI_TIMEOUT_MS) {
            Serial.println("\nTiempo de espera WiFi agotado");
            Serial.println("Revisa SSID, contrasena y que la red sea de 2.4 GHz");
            return false;
        }
        delay(500);
        Serial.print('.');
    }

    Serial.println("\nWiFi conectado");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    return true;
}

void sendHttpError(WiFiClient &client, int code, const char *message) {
    client.printf(
        "HTTP/1.1 %d Error\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "Connection: close\r\n\r\n"
        "%s\r\n",
        code, message);
}

void sendCapture(WiFiClient &client) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb == nullptr) {
        Serial.println("No se pudo capturar un frame");
        sendHttpError(client, 503, "Camera capture failed");
        return;
    }

    client.printf(
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: image/jpeg\r\n"
        "Content-Length: %u\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n\r\n",
        static_cast<unsigned>(fb->len));
    client.write(fb->buf, fb->len);
    esp_camera_fb_return(fb);
}

void sendStatus(WiFiClient &client) {
    client.print(
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "Connection: close\r\n\r\n"
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>ESP32-CAM</title></head><body>"
        "<h1>ESP32-CAM activa</h1>"
        "<p><a href=\"/capture\">Captura JPEG</a></p>"
        "<p><a href=\"http://");
    client.print(WiFi.localIP());
    client.print(":81/stream\">Stream MJPEG</a></p></body></html>");
}

void handleHttpClient() {
    WiFiClient client = httpServer.available();
    if (!client) {
        return;
    }

    client.setTimeout(2);
    const uint32_t startedAt = millis();
    while (client.connected() && !client.available() && millis() - startedAt < 2000) {
        delay(1);
    }

    String request = client.readStringUntil('\r');
    while (client.available()) {
        client.read();
    }

    Serial.print("HTTP: ");
    Serial.println(request);

    if (request.startsWith("GET /capture ")) {
        sendCapture(client);
    } else if (request.startsWith("GET / ")) {
        sendStatus(client);
    } else {
        sendHttpError(client, 404, "Not found");
    }

    client.flush();
    client.stop();
}

void handleStreamClient() {
    WiFiClient client = streamServer.available();
    if (!client) {
        return;
    }

    client.setTimeout(5);
    const uint32_t startedAt = millis();
    while (client.connected() && !client.available() && millis() - startedAt < 2000) {
        delay(1);
    }

    String request = client.readStringUntil('\r');
    while (client.available()) {
        client.read();
    }

    if (!request.startsWith("GET /stream ")) {
        sendHttpError(client, 404, "Not found");
        client.stop();
        return;
    }

    Serial.println("Cliente conectado al stream MJPEG");
    client.print(
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
        "Cache-Control: no-store, no-cache, must-revalidate\r\n"
        "Pragma: no-cache\r\n"
        "Connection: close\r\n\r\n");

    while (client.connected()) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb == nullptr) {
            Serial.println("Fallo de captura; se cierra el stream");
            break;
        }

        const size_t frameLength = fb->len;
        client.printf(
            "--frame\r\n"
            "Content-Type: image/jpeg\r\n"
            "Content-Length: %u\r\n\r\n",
            static_cast<unsigned>(frameLength));

        const size_t written = client.write(fb->buf, frameLength);
        client.print("\r\n");
        esp_camera_fb_return(fb);

        if (written != frameLength || !client.connected()) {
            break;
        }
        delay(1);  // Cede tiempo a las tareas WiFi/RTOS.
    }

    client.stop();
    Serial.println("Cliente desconectado del stream");
}

void setup() {
    Serial.begin(115200);
    Serial.setDebugOutput(false);
    delay(1000);
    Serial.println("\nIniciando ESP32-CAM...");

    if (!initCamera()) {
        Serial.println("Revisa el flex OV2640 y pulsa RESET para reintentar");
        return;
    }

    if (!connectWiFi()) {
        Serial.println("Pulsa RESET despues de corregir la configuracion WiFi");
        return;
    }

    httpServer.begin();
    streamServer.begin();
    Serial.printf("Captura: http://%s/capture\n", WiFi.localIP().toString().c_str());
    Serial.printf("Stream:  http://%s:%u/stream\n",
                  WiFi.localIP().toString().c_str(), STREAM_PORT);
}

void loop() {
    if (WiFi.status() == WL_CONNECTED) {
        handleHttpClient();
        handleStreamClient();
    }
    delay(1);
}
