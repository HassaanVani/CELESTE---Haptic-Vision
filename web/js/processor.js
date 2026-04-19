/**
 * FrameProcessor — converts raw camera frames into a 2x4 motor intensity grid.
 *
 * Pipeline: RGB frame → grayscale → zone averaging → gamma LUT → dead zone →
 *           minimum kick threshold → exponential power curve → 0-255 motor values
 *
 * The curve is designed so that:
 *   - Dim zones (< 15% brightness) produce ZERO motor output (dead zone)
 *   - Anything above the dead zone starts at 40% power (minimum ERM spin-up)
 *   - An exponential ramp from 40% → 100% makes bright zones feel dramatically
 *     stronger than mid-brightness zones
 */
class FrameProcessor {
    constructor() {
        this.gridRows = 2;
        this.gridCols = 4;
        this.gamma = 2.2;              // steeper contrast curve
        this.brightnessFloor = 10;     // lower floor = more sensitivity
        this.brightnessCeil = 180;     // lower ceiling = full power sooner
        this.deadZone = 0.15;          // below 15% normalized = motor OFF
        this.minKick = 0.40;           // above dead zone, start at 40% power
        this.lut = this._buildLUT();
    }

    _buildLUT() {
        const lut = new Uint8Array(256);
        const floor = this.brightnessFloor;
        const ceil = this.brightnessCeil;
        const range = ceil - floor;
        if (range <= 0) return lut;

        for (let i = 0; i < 256; i++) {
            if (i <= floor) { lut[i] = 0; continue; }
            if (i >= ceil)  { lut[i] = 255; continue; }

            // Normalize to 0-1
            const normalized = (i - floor) / range;

            // Apply gamma for contrast
            const curved = Math.pow(normalized, 1.0 / this.gamma);

            // Dead zone: below threshold = fully off
            if (curved < this.deadZone) { lut[i] = 0; continue; }

            // Remap from [deadZone..1] → [minKick..1]
            const active = (curved - this.deadZone) / (1.0 - this.deadZone);
            const boosted = this.minKick + active * (1.0 - this.minKick);

            // Apply exponential power curve for dramatic high-end separation
            const powered = Math.pow(boosted, 1.8);

            lut[i] = Math.min(255, Math.max(0, Math.round(powered * 255)));
        }
        return lut;
    }

    /**
     * Process an ImageData object from the camera canvas.
     * Returns a Uint8Array of length 8 (2 rows x 4 cols), values 0-255.
     */
    process(imageData) {
        const { data, width, height } = imageData;
        const grid = new Uint8Array(this.gridRows * this.gridCols);
        const zoneH = (height / this.gridRows) | 0;
        const zoneW = (width / this.gridCols) | 0;

        // Sample every 4th pixel in each direction for performance
        const step = 4;

        for (let r = 0; r < this.gridRows; r++) {
            for (let c = 0; c < this.gridCols; c++) {
                let sum = 0;
                let count = 0;
                const y0 = r * zoneH;
                const x0 = c * zoneW;

                for (let y = y0; y < y0 + zoneH; y += step) {
                    const rowOff = y * width;
                    for (let x = x0; x < x0 + zoneW; x += step) {
                        const idx = (rowOff + x) << 2;
                        // Luminance from RGB
                        sum += 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2];
                        count++;
                    }
                }

                const mean = (sum / count) | 0;
                grid[r * this.gridCols + c] = this.lut[Math.min(255, Math.max(0, mean))];
            }
        }
        return grid;
    }

    /** Update tuning parameters and rebuild the gamma LUT. */
    updateConfig(cfg) {
        let rebuild = false;
        if (cfg.gamma !== undefined && cfg.gamma !== this.gamma) {
            this.gamma = cfg.gamma; rebuild = true;
        }
        if (cfg.brightnessFloor !== undefined && cfg.brightnessFloor !== this.brightnessFloor) {
            this.brightnessFloor = cfg.brightnessFloor; rebuild = true;
        }
        if (cfg.brightnessCeil !== undefined && cfg.brightnessCeil !== this.brightnessCeil) {
            this.brightnessCeil = cfg.brightnessCeil; rebuild = true;
        }
        if (rebuild) this.lut = this._buildLUT();
    }
}
