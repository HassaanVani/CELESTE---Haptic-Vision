#!/usr/bin/env python3
"""Scan I2C bus to verify PCA9685 boards are visible."""

import subprocess
import sys


def main():
    print("Scanning I2C bus 1...")
    result = subprocess.run(["i2cdetect", "-y", "1"], capture_output=True, text=True)
    print(result.stdout)

    expected = [0x40, 0x41]
    all_ok = True
    for addr in expected:
        hex_str = f"{addr:02x}"
        if hex_str in result.stdout:
            print(f"  [OK] PCA9685 at 0x{hex_str} detected")
        else:
            print(f"  [FAIL] PCA9685 at 0x{hex_str} NOT found")
            print(f"         Check wiring and A0 address jumper on second board")
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
