#!/usr/bin/env python3
"""Measure processing and I2C write latency."""

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.processor import FrameProcessor
from drivers.pca9685 import PCA9685Driver
from config.channel_map import ChannelMap
from config.settings import GRID_ROWS, GRID_COLS, MAX_DUTY_CYCLE


def benchmark_processing(iterations=100):
    """Time the FrameProcessor on synthetic frames."""
    processor = FrameProcessor()
    frame = np.random.randint(0, 256, (480, 640), dtype=np.uint8)

    times = []
    for _ in range(iterations):
        start = time.monotonic()
        processor.process(frame)
        times.append(time.monotonic() - start)

    avg_ms = np.mean(times) * 1000
    print(f"FrameProcessor: {avg_ms:.2f}ms avg ({1000/avg_ms:.0f} Hz potential)")


def benchmark_i2c(iterations=50):
    """Time full 32-channel I2C write."""
    driver = PCA9685Driver()
    driver.init()
    cmap = ChannelMap()

    times = []
    for _ in range(iterations):
        start = time.monotonic()
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                addr, ch = cmap.get(r, c)
                driver.set_duty_cycle(addr, ch, MAX_DUTY_CYCLE // 2)
        times.append(time.monotonic() - start)

    driver.all_off()
    driver.shutdown()

    avg_ms = np.mean(times) * 1000
    print(f"Full I2C write (32 ch): {avg_ms:.2f}ms avg ({1000/avg_ms:.0f} Hz potential)")


def main():
    print("=== Haptic Vision Benchmark ===\n")
    benchmark_processing()
    print()
    benchmark_i2c()


if __name__ == "__main__":
    main()
