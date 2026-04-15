import logging
import threading
import time
import queue

import cv2

from config.settings import (
    CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FPS,
    GAUSSIAN_KERNEL, GAUSSIAN_SIGMA,
)

logger = logging.getLogger(__name__)


class CameraIngest(threading.Thread):
    """Producer thread: captures frames, converts to blurred grayscale,
    pushes to frame_queue. Drops old frames if consumer is slow.

    Tries picamera2 first, falls back to USB webcam (for dry-run / dev)."""

    def __init__(self, frame_queue: queue.Queue, stop_event: threading.Event):
        super().__init__(name="CameraThread", daemon=True)
        self.frame_queue = frame_queue
        self.stop_event = stop_event
        self._picam = None
        self._webcam = None
        self._fps_counter = 0
        self._fps_time = time.monotonic()
        self.actual_fps = 0.0

    def _init_camera(self):
        # Try Pi Camera first
        try:
            from picamera2 import Picamera2
            self._picam = Picamera2()
            config = self._picam.create_still_configuration(
                main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"},
                buffer_count=2,
            )
            self._picam.configure(config)
            self._picam.start()
            time.sleep(1.0)  # let auto-exposure settle
            logger.info("Camera: picamera2")
            return
        except (ImportError, RuntimeError) as e:
            logger.debug(f"picamera2 unavailable: {e}")

        # Fall back to webcam
        self._webcam = cv2.VideoCapture(0)
        self._webcam.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self._webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        if not self._webcam.isOpened():
            raise RuntimeError("No camera available (tried picamera2 and webcam)")
        logger.info("Camera: webcam (fallback)")

    def _capture(self):
        """Returns a BGR frame or None."""
        if self._picam:
            rgb = self._picam.capture_array()
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        ret, frame = self._webcam.read()
        return frame if ret else None

    def run(self):
        try:
            self._init_camera()
        except RuntimeError as e:
            logger.error(f"Camera init failed: {e}")
            self.stop_event.set()
            return

        interval = 1.0 / CAMERA_FPS

        while not self.stop_event.is_set():
            try:
                frame_start = time.monotonic()

                bgr_frame = self._capture()
                if bgr_frame is None:
                    logger.warning("Camera returned empty frame, retrying...")
                    time.sleep(0.05)
                    continue

                gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
                blurred = cv2.GaussianBlur(gray, GAUSSIAN_KERNEL, GAUSSIAN_SIGMA)

                # Non-blocking put with drop-oldest discipline
                try:
                    self.frame_queue.put_nowait(blurred)
                except queue.Full:
                    try:
                        self.frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.frame_queue.put_nowait(blurred)

                # FPS tracking
                self._fps_counter += 1
                elapsed = time.monotonic() - self._fps_time
                if elapsed >= 1.0:
                    self.actual_fps = self._fps_counter / elapsed
                    self._fps_counter = 0
                    self._fps_time = time.monotonic()

                # Maintain target frame rate
                sleep_time = interval - (time.monotonic() - frame_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Camera thread error: {e}")
                self.stop_event.set()
                return

        # Cleanup
        if self._picam:
            self._picam.stop()
            self._picam.close()
        if self._webcam:
            self._webcam.release()
