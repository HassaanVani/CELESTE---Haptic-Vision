import threading
import queue
import signal
import time
import logging

import numpy as np

from config.settings import (
    FRAME_QUEUE_SIZE, PWM_QUEUE_SIZE, SHUTDOWN_TIMEOUT, TARGET_LOOP_HZ,
)
from core.camera import CameraIngest
from core.processor import FrameProcessor
from core.haptic_engine import HapticEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 5.0  # seconds between status logs


class Pipeline:
    """Orchestrates the three-stage pipeline:

    CameraIngest (thread) -> FrameProcessor (main thread) -> HapticEngine (thread)

    Main thread runs processing + signal handling.
    Pass dry_run=True to skip I2C and use webcam fallback.
    """

    def __init__(self, dry_run: bool = False):
        self._dry_run = dry_run
        self._stop_event = threading.Event()
        self._frame_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=FRAME_QUEUE_SIZE)
        self._pwm_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=PWM_QUEUE_SIZE)
        self._processor = FrameProcessor()
        self._camera = None
        self._haptic = None

    def start(self):
        """Start the pipeline. Blocks until stop_event is set."""
        mode = "DRY-RUN" if self._dry_run else "LIVE"
        logger.info(f"Initializing Haptic Vision pipeline ({mode})...")

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._camera = CameraIngest(self._frame_queue, self._stop_event)
        self._haptic = HapticEngine(self._pwm_queue, self._stop_event,
                                    dry_run=self._dry_run)

        self._camera.start()
        self._haptic.start()
        logger.info("Pipeline running. Press Ctrl+C to stop.")

        interval = 1.0 / TARGET_LOOP_HZ
        heartbeat_time = time.monotonic()
        frames_processed = 0

        while not self._stop_event.is_set():
            loop_start = time.monotonic()

            # Check if threads are still alive
            if not self._camera.is_alive() or not self._haptic.is_alive():
                logger.error("Thread died unexpectedly, shutting down")
                break

            try:
                gray_frame = self._frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            duty_grid = self._processor.process(gray_frame)
            frames_processed += 1

            # Push to haptic engine with drop-oldest discipline
            try:
                self._pwm_queue.put_nowait(duty_grid)
            except queue.Full:
                try:
                    self._pwm_queue.get_nowait()
                except queue.Empty:
                    pass
                self._pwm_queue.put_nowait(duty_grid)

            # Periodic heartbeat (info-level, always visible)
            now = time.monotonic()
            if now - heartbeat_time >= HEARTBEAT_INTERVAL:
                cam_fps = self._camera.actual_fps
                hap_hz = self._haptic.actual_hz
                logger.info(
                    f"Status: camera={cam_fps:.1f}fps | "
                    f"haptic={hap_hz:.1f}hz | "
                    f"frames={frames_processed}"
                )
                heartbeat_time = now

            # Rate limit main loop
            sleep_time = interval - (time.monotonic() - loop_start)
            if sleep_time > 0:
                time.sleep(sleep_time)

        self._shutdown()

    def _signal_handler(self, signum, frame):
        logger.info(f"Signal {signum} received, shutting down...")
        self._stop_event.set()

    def _shutdown(self):
        logger.info("Shutting down pipeline...")
        self._stop_event.set()

        if self._camera and self._camera.is_alive():
            self._camera.join(timeout=SHUTDOWN_TIMEOUT)
        if self._haptic and self._haptic.is_alive():
            self._haptic.join(timeout=SHUTDOWN_TIMEOUT)

        logger.info("Pipeline stopped.")
