/**
 * ArduinoConnection — sends motor data to the Arduino Uno WiFi over Web Serial.
 */
class ArduinoConnection {
    constructor() {
        this.port = null;
        this.writer = null;
        this.connected = false;
        this.latency = 0;
        this._pending = false;
    }

    /** Ping/Connect to the Arduino via Serial. */
    async connect() {
        try {
            if (!navigator.serial) {
                alert('Web Serial API is not supported in this browser. Please use Chrome/Edge.');
                return false;
            }
            this.port = await navigator.serial.requestPort();
            await this.port.open({ baudRate: 115200 });
            this.writer = this.port.writable.getWriter();
            this.connected = true;
            return true;
        } catch (e) {
            console.error('Serial connection failed:', e);
            this.connected = false;
            return false;
        }
    }

    async disconnect() {
        if (this.writer) {
            this.writer.releaseLock();
            this.writer = null;
        }
        if (this.port) {
            await this.port.close();
            this.port = null;
        }
        this.connected = false;
    }

    /**
     * Send an 8-byte motor grid to the Arduino via Serial.
     * Protocol: [0xAA, 0x55, 8 bytes of grid]
     */
    async sendMotorData(grid) {
        if (!this.connected || !this.writer || this._pending) return false;
        this._pending = true;

        const start = performance.now();
        try {
            // Frame: 2 bytes header + 8 bytes payload
            const frame = new Uint8Array(10);
            frame[0] = 0xAA;
            frame[1] = 0x55;
            frame.set(grid, 2);

            await this.writer.write(frame);
            this.latency = Math.round(performance.now() - start);
            return true;
        } catch (e) {
            console.error('Serial write failed:', e);
            this.connected = false;
            return false;
        } finally {
            this._pending = false;
        }
    }
}
