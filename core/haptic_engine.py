import logging
import threading
import time
import queue

import numpy as np

from config.settings import GRID_ROWS, GRID_COLS, MAX_DUTY_CYCLE
from config.channel_map import ChannelMap

logger = logging.getLogger(__name__)


class HapticEngine(threading.Thread):
    """Consumer thread: reads duty-cycle grids from pwm_queue,
    writes changed channels to PCA9685 boards via I2C (delta updates).

    In dry_run mode, logs duty grid summaries instead of writing I2C."""

    def __init__(self, pwm_queue: queue.Queue, stop_event: threading.Event,
                 dry_run: bool = False):
        super().__init__(name="HapticThread", daemon=True)
        self.pwm_queue = pwm_queue
        self.stop_event = stop_event
        self._dry_run = dry_run
        self._driver = None
        self._channel_map = ChannelMap()
        self._last_grid = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.uint16)
        self._update_count = 0
        self._update_time = time.monotonic()
        self.actual_hz = 0.0

    def run(self):
        if not self._dry_run:
            try:
                from drivers.pca9685 import PCA9685Driver
                self._driver = PCA9685Driver()
                self._driver.init()
                logger.info("Haptic engine: I2C hardware")
            except Exception as e:
                logger.error(f"I2C init failed: {e}")
                self.stop_event.set()
                return
        else:
            logger.info("Haptic engine: dry-run (no I2C)")

        while not self.stop_event.is_set():
            try:
                duty_grid = self.pwm_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                if self._dry_run:
                    self._log_grid(duty_grid)
                else:
                    self._write_delta(duty_grid)
                self._last_grid = duty_grid.copy()
            except Exception as e:
                logger.error(f"Haptic write error: {e}")
                self.stop_event.set()
                return

            # Hz tracking
            self._update_count += 1
            elapsed = time.monotonic() - self._update_time
            if elapsed >= 1.0:
                self.actual_hz = self._update_count / elapsed
                self._update_count = 0
                self._update_time = time.monotonic()

        # Cleanup
        if self._driver:
            self._driver.shutdown()

    def _write_delta(self, duty_grid: np.ndarray):
        """Only write channels whose duty cycle changed since last frame."""
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                if duty_grid[r, c] != self._last_grid[r, c]:
                    addr, channel = self._channel_map.get(r, c)
                    self._driver.set_duty_cycle(addr, channel, int(duty_grid[r, c]))

    def _log_grid(self, duty_grid: np.ndarray):
        """Log a compact summary of the duty grid (dry-run mode)."""
        pct_grid = (duty_grid.astype(float) / MAX_DUTY_CYCLE * 100).astype(int)
        changed = int(np.sum(duty_grid != self._last_grid))
        avg_pct = int(np.mean(pct_grid))
        max_pct = int(np.max(pct_grid))
        logger.debug(f"Grid: avg={avg_pct}% max={max_pct}% changed={changed}/32")
