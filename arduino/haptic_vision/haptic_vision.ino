/*
 * HapticVision — Arduino Uno WiFi Firmware (Serial Mode)
 *
 * Receives a 10-byte motor grid frame from the browser over Web Serial
 * [0xAA, 0x55, 8 bytes of grid] and drives a single PCA9685 PWM board.
 */

#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// ── PCA9685 ────────────────────────────────────────
static const uint8_t BOARD_ADDR_0 = 0x40;
static const uint16_t PWM_FREQ    = 20;      // 20 Hz — maximum heavy rumble torque

Adafruit_PWMServoDriver pwm0 = Adafruit_PWMServoDriver(BOARD_ADDR_0);

// ── Grid ───────────────────────────────────────────
static const uint8_t GRID_ROWS  = 2;
static const uint8_t GRID_COLS  = 4;
static const uint8_t NUM_MOTORS = GRID_ROWS * GRID_COLS;  // 8

// ── Safety ─────────────────────────────────────────
static const unsigned long WATCHDOG_MS = 2000;  // kill motors after 2 s silence
unsigned long lastCommandTime = 0;

// ── Motor state ────────────────────────────────────
uint8_t currentMotors[NUM_MOTORS] = {0};

enum State { WAIT_AA, WAIT_55, READ_DATA };
State state = WAIT_AA;
uint8_t motorData[NUM_MOTORS];
uint8_t dataIndex = 0;


void setup() {
    Serial.begin(115200);

    // Wait until serial is open, up to 3 seconds
    while (!Serial && millis() < 3000);

    // ── I2C + PCA9685 ──────────────────────────────
    Wire.begin();
    pwm0.begin();
    pwm0.setPWMFreq(PWM_FREQ);
    allMotorsOff();
}

void loop() {
    // Watchdog
    if (lastCommandTime > 0 && millis() - lastCommandTime > WATCHDOG_MS) {
        allMotorsOff();
        lastCommandTime = 0;
    }

    // Process serial data
    while (Serial.available() > 0) {
        uint8_t b = Serial.read();

        switch (state) {
            case WAIT_AA:
                if (b == 0xAA) state = WAIT_55;
                break;
                
            case WAIT_55:
                if (b == 0x55) {
                    state = READ_DATA;
                    dataIndex = 0;
                } else if (b == 0xAA) {
                    state = WAIT_55;
                } else {
                    state = WAIT_AA;
                }
                break;
                
            case READ_DATA:
                motorData[dataIndex++] = b;
                if (dataIndex == NUM_MOTORS) {
                    applyMotors(motorData);
                    lastCommandTime = millis();
                    state = WAIT_AA;
                }
                break;
        }
    }
}

// ── Motor intensity curve ──────────────────────────
// Dead zone: values below this are treated as fully OFF
static const uint8_t DEAD_ZONE = 25;
// Minimum duty cycle when motor is active (40% of 4095)
static const uint16_t MIN_DUTY = 1638;
// Maximum duty cycle
static const uint16_t MAX_DUTY = 4095;

void applyMotors(uint8_t *values) {
    for (uint8_t i = 0; i < NUM_MOTORS; i++) {
        // Only update channels that changed
        if (values[i] == currentMotors[i]) continue;
        currentMotors[i] = values[i];

        uint16_t duty12;
        if (values[i] < DEAD_ZONE) {
            // Dead zone: motor fully off
            duty12 = 0;
        } else {
            // Remap [DEAD_ZONE..255] → [0..255]
            uint16_t remapped = ((uint16_t)(values[i] - DEAD_ZONE) * 255) / (255 - DEAD_ZONE);
            // Quadratic curve for dramatic separation: (x/255)^2 * (MAX-MIN) + MIN
            uint32_t squared = (uint32_t)remapped * remapped;  // 0..65025
            duty12 = MIN_DUTY + (uint16_t)((squared * (uint32_t)(MAX_DUTY - MIN_DUTY)) / 65025UL);
        }

        pwm0.setPWM(i, 0, duty12);
    }
}

void allMotorsOff() {
    for (uint8_t ch = 0; ch < 16; ch++) {
        pwm0.setPWM(ch, 0, 0);
    }
    memset(currentMotors, 0, NUM_MOTORS);
}
