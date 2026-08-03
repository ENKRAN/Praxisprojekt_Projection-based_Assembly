from typing import Optional
import numpy as np

class RealSenseCamera:
    def __init__(self, width: int, height: int, fps: int):
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)

        self._pipeline = None
        self._config = None
        self._running = False

    def start(self) -> None:
        import pyrealsense2 as rs
        self._pipeline = rs.pipeline()
        self._config = rs.config()

        self._config.enable_stream(rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps)
        self._pipeline.start(self._config)
        self._running = True

    def stop(self) -> None:
        if self._pipeline is not None:
            try:
                self._pipeline.stop()
            except Exception:
                pass
        self._running = False
        self._pipeline = None
        self._config = None

    def read(self) -> Optional[np.ndarray]:
        if not self._running or self._pipeline is None:
            return None

        try:
            frames = self._pipeline.wait_for_frames(timeout_ms=1000)
            color = frames.get_color_frame()
            if not color:
                return None
            frame = np.asanyarray(color.get_data())  # already BGR8
            return frame
        except Exception:
            return None
