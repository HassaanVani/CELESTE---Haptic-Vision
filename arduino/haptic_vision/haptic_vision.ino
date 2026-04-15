/*
 * HapticVision — Arduino Uno WiFi Firmware
 *
 * Receives a 32-byte motor grid from the browser over HTTP and drives
 * two daisy-chained PCA9685 PWM boards (0x40, 0x41) controlling 32 ERM motors.
 *
 * Endpoints:
 *   POST /motors  — 32 raw bytes, one per motor (0-255)
 *   GET  /status  — JSON health check
 *   OPTIONS *     — CORS preflight
 *
 * Board: Arduino Uno R4 WiFi  (also works with Uno WiFi Rev2 — swap WiFiS3 → WiFiNINA)
 */

#include <WiFiS3.h>        // Arduino Uno R4 WiFi — change to <WiFiNINA.h> for Rev2
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// ── WiFi credentials (edit these) ──────────────────
char ssid[] = "YOUR_WIFI_SSID";
char pass[] = "YOUR_WIFI_PASSWORD";

// ── PCA9685 boards ─────────────────────────────────
static const uint8_t BOARD_ADDR_0 = 0x40;   // rows 0-1
static const uint8_t BOARD_ADDR_1 = 0x41;   // rows 2-3
static const uint16_t PWM_FREQ    = 1000;    // 1 kHz — above ERM audible whine

Adafruit_PWMServoDriver pwm0 = Adafruit_PWMServoDriver(BOARD_ADDR_0);
Adafruit_PWMServoDriver pwm1 = Adafruit_PWMServoDriver(BOARD_ADDR_1);

// ── Grid ───────────────────────────────────────────
static const uint8_t GRID_ROWS  = 4;
static const uint8_t GRID_COLS  = 8;
static const uint8_t NUM_MOTORS = GRID_ROWS * GRID_COLS;  // 32

// ── Network ────────────────────────────────────────
WiFiServer server(80);
static const uint16_t HTTP_BUF_SIZE = 512;

// ── Safety ─────────────────────────────────────────
static const unsigned long WATCHDOG_MS = 2000;  // kill motors after 2 s silence
unsigned long lastCommandTime = 0;

// ── Motor state ────────────────────────────────────
uint8_t currentMotors[NUM_MOTORS] = {0};

// ──────────────────────────────────────────────────────────────
// SETUP
// ──────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    while (!Serial && millis() < 3000);  // wait up to 3 s for serial monitor

    Serial.println(F("\n=== HapticVision Firmware ==="));

    // ── I2C + PCA9685 ──────────────────────────────
    Wire.begin();
    pwm0.begin();
    pwm0.setPWMFreq(PWM_FREQ);
    pwm1.begin();
    pwm1.setPWMFreq(PWM_FREQ);
    allMotorsOff();
    Serial.println(F("[OK] PCA9685 boards initialised"));

    // ── WiFi ───────────────────────────────────────
    Serial.print(F("Connecting to WiFi"));
    int status = WiFi.begin(ssid, pass);
    while (status != WL_CONNECTED) {
        Serial.print('.');
        delay(1000);
        status = WiFi.begin(ssid, pass);
    }
    Serial.println();
    Serial.print(F("[OK] IP address: "));
    Serial.println(WiFi.localIP());

    // ── HTTP server ────────────────────────────────
    server.begin();
    Serial.println(F("[OK] HTTP server listening on port 80"));
    Serial.println(F("Ready — waiting for browser connection..."));
}

// ──────────────────────────────────────────────────────────────
// LOOP
// ──────────────────────────────────────────────────────────────
void loop() {
    // Watchdog — turn off motors if browser stops sending
    if (lastCommandTime > 0 && millis() - lastCommandTime > WATCHDOG_MS) {
        allMotorsOff();
        lastCommandTime = 0;
    }

    WiFiClient client = server.available();
    if (client) {
        handleClient(client);
    }
}

// ──────────────────────────────────────────────────────────────
// HTTP HANDLER
// ──────────────────────────────────────────────────────────────
void handleClient(WiFiClient &client) {
    // Read request line + headers
    char buf[HTTP_BUF_SIZE];
    int len = 0;
    bool headersDone = false;
    int contentLength = 0;
    unsigned long start = millis();

    // Read headers (line by line)
    while (client.connected() && millis() - start < 500) {
        if (!client.available()) { delay(1); continue; }

        char c = client.read();
        if (len < HTTP_BUF_SIZE - 1) buf[len++] = c;

        // Detect end of headers (\r\n\r\n)
        if (len >= 4 &&
            buf[len-4] == '\r' && buf[len-3] == '\n' &&
            buf[len-2] == '\r' && buf[len-1] == '\n') {
            headersDone = true;
            break;
        }
    }
    buf[len] = '\0';

    if (!headersDone) { client.stop(); return; }

    // Parse method and path from first line
    // e.g. "POST /motors HTTP/1.1\r\n..."
    bool isPOST   = (buf[0] == 'P');
    bool isGET     = (buf[0] == 'G');
    bool isOPTIONS = (buf[0] == 'O');

    bool pathMotors = (strstr(buf, "/motors") != NULL);
    bool pathStatus = (strstr(buf, "/status") != NULL);

    // Extract Content-Length
    char *clHeader = strstr(buf, "Content-Length: ");
    if (!clHeader) clHeader = strstr(buf, "content-length: ");
    if (clHeader) {
        contentLength = atoi(clHeader + 16);
    }

    // ── OPTIONS (CORS preflight) ───────────────────
    if (isOPTIONS) {
        sendCorsHeaders(client, "204 No Content");
        client.println();
        client.stop();
        return;
    }

    // ── GET /status ────────────────────────────────
    if (isGET && pathStatus) {
        sendCorsHeaders(client, "200 OK");
        client.println(F("Content-Type: application/json"));
        client.println();
        client.print(F("{\"ok\":true,\"ip\":\""));
        client.print(WiFi.localIP());
        client.print(F("\",\"rssi\":"));
        client.print(WiFi.RSSI());
        client.print(F(",\"uptime\":"));
        client.print(millis() / 1000);
        client.println(F("}"));
        client.stop();
        return;
    }

    // ── POST /motors ───────────────────────────────
    if (isPOST && pathMotors) {
        if (contentLength != NUM_MOTORS) {
            sendCorsHeaders(client, "400 Bad Request");
            client.println(F("Content-Type: text/plain"));
            client.println();
            client.print(F("Expected "));
            client.print(NUM_MOTORS);
            client.println(F(" bytes"));
            client.stop();
            return;
        }

        // Read body
        uint8_t motorData[NUM_MOTORS];
        int bytesRead = 0;
        unsigned long bodyStart = millis();
        while (bytesRead < NUM_MOTORS && millis() - bodyStart < 200) {
            if (client.available()) {
                motorData[bytesRead++] = client.read();
            } else {
                delay(1);
            }
        }

        if (bytesRead == NUM_MOTORS) {
            applyMotors(motorData);
            lastCommandTime = millis();

            sendCorsHeaders(client, "200 OK");
            client.println(F("Content-Type: text/plain"));
            client.println();
            client.println(F("OK"));
        } else {
            sendCorsHeaders(client, "400 Bad Request");
            client.println();
            client.println(F("Incomplete body"));
        }
        client.stop();
        return;
    }

    // ── 404 ────────────────────────────────────────
    sendCorsHeaders(client, "404 Not Found");
    client.println();
    client.stop();
}

// ──────────────────────────────────────────────────────────────
// CORS HEADERS
// ──────────────────────────────────────────────────────────────
void sendCorsHeaders(WiFiClient &client, const char *status) {
    client.print(F("HTTP/1.1 "));
    client.println(status);
    client.println(F("Access-Control-Allow-Origin: *"));
    client.println(F("Access-Control-Allow-Methods: GET, POST, OPTIONS"));
    client.println(F("Access-Control-Allow-Headers: Content-Type"));
    client.println(F("Connection: close"));
}

// ──────────────────────────────────────────────────────────────
// MOTOR CONTROL
// ──────────────────────────────────────────────────────────────

/**
 * Map the flat 32-byte array to PCA9685 channels.
 *
 * Index layout (matches the Raspberry Pi channel_map):
 *   [0..7]   → Board 0x40, channels 0-7   (row 0 — wrist)
 *   [8..15]  → Board 0x40, channels 8-15  (row 1)
 *   [16..23] → Board 0x41, channels 0-7   (row 2)
 *   [24..31] → Board 0x41, channels 8-15  (row 3 — elbow)
 */
void applyMotors(uint8_t *values) {
    for (uint8_t i = 0; i < NUM_MOTORS; i++) {
        // Only update channels that changed (reduces I2C traffic)
        if (values[i] == currentMotors[i]) continue;
        currentMotors[i] = values[i];

        uint16_t duty12 = ((uint16_t)values[i] * 4095) / 255;   // 0-255 → 0-4095
        uint8_t  channel = i % 16;

        if (i < 16) {
            pwm0.setPWM(channel, 0, duty12);
        } else {
            pwm1.setPWM(channel, 0, duty12);
        }
    }
}

void allMotorsOff() {
    for (uint8_t ch = 0; ch < 16; ch++) {
        pwm0.setPWM(ch, 0, 0);
        pwm1.setPWM(ch, 0, 0);
    }
    memset(currentMotors, 0, NUM_MOTORS);
}
