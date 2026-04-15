#!/usr/bin/env python3
"""Test all 32 motors with sweep and wave patterns."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from drivers.pca9685 import PCA9685Driver
from config.channel_map import ChannelMap
from config.settings import GRID_ROWS, GRID_COLS, MAX_DUTY_CYCLE

HALF_DUTY = MAX_DUTY_CYCLE // 2


def sweep(driver, cmap):
    """Activate each motor briefly in raster order."""
    print("Sequential sweep...")
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            addr, ch = cmap.get(row, col)
            driver.set_duty_cycle(addr, ch, HALF_DUTY)
            time.sleep(0.15)
            driver.set_duty_cycle(addr, ch, 0)


def row_wave(driver, cmap):
    """Activate full rows in sequence."""
    print("Row wave...")
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            addr, ch = cmap.get(row, col)
            driver.set_duty_cycle(addr, ch, HALF_DUTY)
        time.sleep(0.5)
        for col in range(GRID_COLS):
            addr, ch = cmap.get(row, col)
            driver.set_duty_cycle(addr, ch, 0)


def col_wave(driver, cmap):
    """Activate full columns in sequence."""
    print("Column wave...")
    for col in range(GRID_COLS):
        for row in range(GRID_ROWS):
            addr, ch = cmap.get(row, col)
            driver.set_duty_cycle(addr, ch, HALF_DUTY)
        time.sleep(0.3)
        for row in range(GRID_ROWS):
            addr, ch = cmap.get(row, col)
            driver.set_duty_cycle(addr, ch, 0)


def intensity_ramp(driver, cmap):
    """All motors simultaneously, ramping from off to full."""
    print("Intensity ramp (all motors)...")
    for duty in range(0, MAX_DUTY_CYCLE, 256):
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                addr, ch = cmap.get(row, col)
                driver.set_duty_cycle(addr, ch, duty)
        time.sleep(0.1)
    driver.all_off()


def main():
    driver = PCA9685Driver()
    driver.init()
    cmap = ChannelMap()

    try:
        sweep(driver, cmap)
        time.sleep(0.5)
        row_wave(driver, cmap)
        time.sleep(0.5)
        col_wave(driver, cmap)
        time.sleep(0.5)
        intensity_ramp(driver, cmap)
    except KeyboardInterrupt:
        pass
    finally:
        driver.all_off()
        driver.shutdown()
        print("Done.")


if __name__ == "__main__":
    main()
