#!/usr/bin/env python3
"""Haptic Vision - Sensory Substitution System

Translates camera input into a 32-point haptic map on the forearm,
enabling visually impaired users to perceive depth and obstacles through touch.
"""

import argparse
import logging

from core.pipeline import Pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Haptic Vision: camera-to-vibration sensory substitution",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run camera + processing without I2C output (webcam fallback, no hardware needed)",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    pipeline = Pipeline(dry_run=args.dry_run)
    pipeline.start()


if __name__ == "__main__":
    main()
