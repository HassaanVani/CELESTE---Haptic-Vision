#!/usr/bin/env python3
"""Interactive motor calibration tool.
Activates one motor at a time to verify physical grid position."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from drivers.pca9685 import PCA9685Driver
from config.channel_map import ChannelMap
from config.settings import GRID_ROWS, GRID_COLS, MAX_DUTY_CYCLE


def main():
    driver = PCA9685Driver()
    driver.init()
    channel_map = ChannelMap()

    print("=== Motor Calibration Tool ===")
    print("Each motor will buzz for 1 second.")
    print("Verify the physical position matches the label.")
    print("Press Enter to advance, 'q' to quit.\n")

    try:
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                addr, ch = channel_map.get(row, col)
                label = f"Row {row}, Col {col} (Board 0x{addr:02x}, Ch {ch})"
                response = input(f"Next: {label} -- Press Enter...")
                if response.strip().lower() == "q":
                    return

                driver.set_duty_cycle(addr, ch, MAX_DUTY_CYCLE // 2)
                time.sleep(1.0)
                driver.set_duty_cycle(addr, ch, 0)

    except KeyboardInterrupt:
        pass
    finally:
        driver.all_off()
        driver.shutdown()
        print("\nCalibration complete.")


if __name__ == "__main__":
    main()
