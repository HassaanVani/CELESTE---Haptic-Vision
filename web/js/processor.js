/**
 * FrameProcessor — converts raw camera frames into a 4x8 motor intensity grid.
 *
 * Pipeline: RGB frame → grayscale → zone averaging → gamma LUT → 0-255 motor values
 */
class FrameProcessor {
    constructor() {
        this.gridRows = 4;
        this.gridCols = 8;
        this.gamma = 1.5;
        this.brightnessFloor = 20;
        this.brightnessCeil = 240;
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
            const normalized = (i - floor) / range;
            const curved = Math.pow(normalized, 1.0 / this.gamma);
            lut[i] = Math.min(255, Math.round(curved * 255));
        }
        return lut;
    }

    /**
     * Process an ImageData object from the camera canvas.
     * Returns a Uint8Array of length 32 (4 rows x 8 cols), values 0-255.
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
