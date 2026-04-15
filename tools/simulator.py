#!/usr/bin/env python3
"""Haptic Vision Dashboard / Simulator

3-panel live view:
  Left:          Raw camera feed
  Top-right:     Processed grayscale with 8x4 grid overlay + zone percentages
  Bottom-right:  4x8 circle array showing real-time motor intensities

Works with Pi Camera (picamera2) or falls back to USB webcam for dev/demo.
Requires opencv-python (NOT opencv-python-headless) for the GUI window.

Usage:
  cd ~/haptic-vision
  python tools/simulator.py          # auto-detect camera
  python tools/simulator.py --webcam  # force webcam
"""

import argparse
import sys
import os
import time

import cv2
import numpy as np

# Allow running from project root or tools/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.settings import (
    CAMERA_WIDTH, CAMERA_HEIGHT,
    GAUSSIAN_KERNEL, GAUSSIAN_SIGMA,
    GRID_ROWS, GRID_COLS, MAX_DUTY_CYCLE,
)
from core.processor import FrameProcessor

# Layout constants
FEED_W, FEED_H = 640, 480
SIDE_W = 320
PROC_H = 240
MOTOR_H = 240
WINDOW_W = FEED_W + SIDE_W  # 960
WINDOW_H = FEED_H           # 480


class Camera:
    """Unified camera interface: picamera2 on Pi, OpenCV webcam elsewhere."""

    def __init__(self, force_webcam=False):
        self._cam = None
        self._type = None

        if not force_webcam:
            try:
                from picamera2 import Picamera2
                self._cam = Picamera2()
                config = self._cam.create_still_configuration(
                    main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"},
                    buffer_count=2,
                )
                self._cam.configure(config)
                self._cam.start()
                time.sleep(1.0)
                self._type = "picamera2"
                return
            except (ImportError, RuntimeError):
                pass

        self._cam = cv2.VideoCapture(0)
        self._cam.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self._cam.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        if not self._cam.isOpened():
            print("ERROR: No camera available (tried picamera2 and webcam)")
            sys.exit(1)
        self._type = "webcam"

    @property
    def source(self):
        return self._type

    def read(self):
        """Returns a BGR frame (OpenCV native) or None on failure."""
        if self._type == "picamera2":
            rgb = self._cam.capture_array()
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        else:
            ret, frame = self._cam.read()
            return frame if ret else None

    def release(self):
        if self._type == "picamera2":
            self._cam.stop()
            self._cam.close()
        else:
            self._cam.release()


def draw_processed_panel(blurred, duty_grid):
    """Grayscale frame with grid lines and zone intensity percentages."""
    resized = cv2.resize(blurred, (SIDE_W, PROC_H))
    panel = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
    h, w = panel.shape[:2]

    cell_h = h // GRID_ROWS
    cell_w = w // GRID_COLS

    # Grid lines
    for r in range(1, GRID_ROWS):
        y = r * cell_h
        cv2.line(panel, (0, y), (w, y), (0, 220, 220), 1)
    for c in range(1, GRID_COLS):
        x = c * cell_w
        cv2.line(panel, (x, 0), (x, h), (0, 220, 220), 1)

    # Zone percentages
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            cx = c * cell_w + cell_w // 2
            cy = r * cell_h + cell_h // 2
            pct = int(duty_grid[r, c] / MAX_DUTY_CYCLE * 100)
            cv2.putText(
                panel, f"{pct}%", (cx - 14, cy + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1,
            )

    return panel


def draw_motor_panel(duty_grid):
    """4-row x 8-col circle array visualizing motor vibration intensity."""
    panel = np.zeros((MOTOR_H, SIDE_W, 3), dtype=np.uint8)

    margin_x, margin_y = 20, 28
    usable_w = SIDE_W - 2 * margin_x
    usable_h = MOTOR_H - 2 * margin_y
    cell_w = usable_w // GRID_COLS
    cell_h = usable_h // GRID_ROWS
    max_r = min(cell_w, cell_h) // 2 - 3

    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            cx = margin_x + c * cell_w + cell_w // 2
            cy = margin_y + r * cell_h + cell_h // 2
            intensity = duty_grid[r, c] / MAX_DUTY_CYCLE

            # Outer ring (always visible)
            cv2.circle(panel, (cx, cy), max_r, (50, 50, 50), 2)

            # Filled circle scales in size and brightness with intensity
            if intensity > 0.01:
                g = int(intensity * 255)
                b = int(intensity * 40)
                fill_r = max(3, int(max_r * (0.3 + 0.7 * intensity)))
                cv2.circle(panel, (cx, cy), fill_r, (b, g, 0), -1)

                # Bright border glow at high intensity
                if intensity > 0.4:
                    glow = (int(b * 0.4), int(g * 0.4), 0)
                    cv2.circle(panel, (cx, cy), max_r, glow, 2)

    # Orientation labels
    cv2.putText(panel, "WRIST", (SIDE_W // 2 - 22, 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 120), 1)
    cv2.putText(panel, "ELBOW", (SIDE_W // 2 - 24, MOTOR_H - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 120), 1)
    cv2.putText(panel, "L", (4, MOTOR_H // 2 + 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 120), 1)
    cv2.putText(panel, "R", (SIDE_W - 14, MOTOR_H // 2 + 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 120, 120), 1)

    return panel


def main():
    parser = argparse.ArgumentParser(description="Haptic Vision Dashboard")
    parser.add_argument("--webcam", action="store_true", help="Force webcam (skip picamera2)")
    args = parser.parse_args()

    camera = Camera(force_webcam=args.webcam)
    processor = FrameProcessor()

    print(f"Camera source: {camera.source}")
    print("Press 'q' to quit")

    fps_time = time.monotonic()
    fps_count = 0
    fps_display = 0.0

    while True:
        bgr_frame = camera.read()
        if bgr_frame is None:
            break

        # Process (same pipeline as the real system)
        gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, GAUSSIAN_KERNEL, GAUSSIAN_SIGMA)
        duty_grid = processor.process(blurred)

        # === Build composite dashboard ===
        canvas = np.zeros((WINDOW_H, WINDOW_W, 3), dtype=np.uint8)

        # Left: live camera feed
        feed = cv2.resize(bgr_frame, (FEED_W, FEED_H))
        canvas[0:FEED_H, 0:FEED_W] = feed

        # Top-right: processed grayscale with grid overlay
        proc_panel = draw_processed_panel(blurred, duty_grid)
        canvas[0:PROC_H, FEED_W:WINDOW_W] = proc_panel

        # Bottom-right: motor intensity circles
        motor_panel = draw_motor_panel(duty_grid)
        canvas[PROC_H:PROC_H + MOTOR_H, FEED_W:WINDOW_W] = motor_panel

        # Divider line between right panels
        cv2.line(canvas, (FEED_W, PROC_H), (WINDOW_W, PROC_H), (80, 80, 80), 1)

        # Vertical divider
        cv2.line(canvas, (FEED_W, 0), (FEED_W, WINDOW_H), (80, 80, 80), 1)

        # FPS counter
        fps_count += 1
        elapsed = time.monotonic() - fps_time
        if elapsed >= 1.0:
            fps_display = fps_count / elapsed
            fps_count = 0
            fps_time = time.monotonic()
        cv2.putText(canvas, f"{fps_display:.0f} FPS", (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Panel titles
        cv2.putText(canvas, "LIVE FEED", (FEED_W // 2 - 55, FEED_H - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
        cv2.putText(canvas, "DETECTION GRID", (FEED_W + SIDE_W // 2 - 62, PROC_H - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
        cv2.putText(canvas, "MOTOR MAP", (FEED_W + SIDE_W // 2 - 48, PROC_H + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

        # Title bar
        cv2.putText(canvas, "HAPTIC VISION", (FEED_W + SIDE_W // 2 - 115, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 180, 0), 1)

        cv2.imshow("Haptic Vision Dashboard", canvas)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()
    print("Dashboard closed.")


if __name__ == "__main__":
    main()
