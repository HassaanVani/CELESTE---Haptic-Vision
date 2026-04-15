/**
 * ArduinoConnection — sends motor data to the Arduino Uno WiFi over HTTP.
 *
 * Protocol:
 *   POST /motors  — body is 32 raw bytes (Uint8Array), one per motor 0-255
 *   GET  /status  — returns JSON health check
 */
class ArduinoConnection {
    constructor() {
        this.ip = '192.168.1.100';
        this.port = 80;
        this.connected = false;
        this.latency = 0;
        this._pending = false;          // avoid stacking requests
    }

    get baseUrl() {
        return `http://${this.ip}:${this.port}`;
    }

    updateAddress(ip, port) {
        this.ip = ip;
        this.port = port || 80;
        this.connected = false;
    }

    /**
     * Send a 32-byte motor grid to the Arduino.
     * Returns true on success. Skips if a previous request is still in flight.
     */
    async sendMotorData(grid) {
        if (this._pending) return false;
        this._pending = true;

        const start = performance.now();
        try {
            const resp = await fetch(this.baseUrl + '/motors', {
                method: 'POST',
                headers: { 'Content-Type': 'application/octet-stream' },
                body: grid.buffer,
                signal: AbortSignal.timeout(300)
            });
            this.latency = Math.round(performance.now() - start);
            this.connected = resp.ok;
            return resp.ok;
        } catch (_) {
            this.connected = false;
            this.latency = 0;
            return false;
        } finally {
            this._pending = false;
        }
    }

    /** Ping the Arduino to verify connectivity. */
    async checkStatus() {
        try {
            const resp = await fetch(this.baseUrl + '/status', {
                signal: AbortSignal.timeout(2000)
            });
            if (resp.ok) {
                this.connected = true;
                return await resp.json();
            }
        } catch (_) { /* unreachable */ }
        this.connected = false;
        return null;
    }
}
