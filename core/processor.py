import numpy as np

from config.settings import (
    GRID_ROWS, GRID_COLS,
    BRIGHTNESS_FLOOR, BRIGHTNESS_CEIL, GAMMA,
    MIN_DUTY_CYCLE, MAX_DUTY_CYCLE,
)


class FrameProcessor:
    """Divides a grayscale frame into an 8x4 grid and maps mean brightness
    per zone to 12-bit PWM duty cycles via a precomputed gamma LUT."""

    def __init__(self):
        self._lut = self._build_gamma_lut()

    def _build_gamma_lut(self) -> np.ndarray:
        """256-entry lookup: grayscale (0-255) -> duty cycle (0-4095)."""
        lut = np.zeros(256, dtype=np.uint16)
        for i in range(256):
            if i < BRIGHTNESS_FLOOR:
                lut[i] = MIN_DUTY_CYCLE
            elif i > BRIGHTNESS_CEIL:
                lut[i] = MAX_DUTY_CYCLE
            else:
                normalized = (i - BRIGHTNESS_FLOOR) / (BRIGHTNESS_CEIL - BRIGHTNESS_FLOOR)
                curved = normalized ** (1.0 / GAMMA)
                lut[i] = int(curved * MAX_DUTY_CYCLE)
        return lut

    def process(self, gray_frame: np.ndarray) -> np.ndarray:
        """Divide frame into GRID_ROWS x GRID_COLS zones, compute mean
        brightness per zone, map to duty cycles.

        Returns:
            (GRID_ROWS x GRID_COLS) uint16 array with values 0-4095.
        """
        h, w = gray_frame.shape
        row_step = h // GRID_ROWS
        col_step = w // GRID_COLS

        duty_grid = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.uint16)

        for r in range(GRID_ROWS):
            y_start = r * row_step
            y_end = (r + 1) * row_step if r < GRID_ROWS - 1 else h
            for c in range(GRID_COLS):
                x_start = c * col_step
                x_end = (c + 1) * col_step if c < GRID_COLS - 1 else w
                zone = gray_frame[y_start:y_end, x_start:x_end]
                mean_brightness = int(np.mean(zone))
                duty_grid[r, c] = self._lut[mean_brightness]

        return duty_grid
