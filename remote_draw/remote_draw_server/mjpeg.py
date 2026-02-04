import time
from typing import Iterator
import cv2

from .state import SharedState
from .config import AppConfig

def mjpeg_generator(state: SharedState, cfg: AppConfig) -> Iterator[bytes]:
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(cfg.jpeg_quality)]

    while True:
        with state.lock:
            frame = None if state.latest_frame_bgr is None else state.latest_frame_bgr.copy()

        if frame is None:
            time.sleep(0.02)
            continue

        ok, jpg = cv2.imencode(".jpg", frame, encode_params)
        if not ok:
            time.sleep(0.02)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
        )
