"""
Shared Memory Camera Client.

Reads camera frames from the named shared memory segments written by
camera_server.py (or app.hardware.camera_server).  Any number of
processes can read simultaneously without touching the hardware.

Drop-in replacement for:
    - CameraService  (used by VisionWorker in PyQt6 app)
    - RealSenseCamera (used by remote_draw_server)

Both interfaces are supported:

    # CameraService interface (context manager):
    with SharedCameraClient() as cam:
        ok, color, depth = cam.getFrames()
        scale = cam.depth_scale

    # RealSenseCamera interface:
    cam = SharedCameraClient()
    cam.start()
    frame = cam.read()   # BGR ndarray | None
    cam.stop()
"""

import struct
import time
from multiprocessing import shared_memory
from typing import Optional, Tuple

import numpy as np

# --- Must match camera_server.py constants ---
SHM_COLOR = "cam_color"
SHM_DEPTH = "cam_depth"
SHM_META  = "cam_meta"

FRAME_WIDTH  = 1280
FRAME_HEIGHT = 720

_OFF_DEPTH_SCALE = 0
_OFF_TIMESTAMP   = 8
_OFF_FRAME_CTR   = 16
_OFF_RUNNING     = 24

# How old (seconds) a frame may be before getFrames() considers it stale
_STALE_THRESHOLD = 1.0


class SharedCameraClient:
    """
    Read-only client for the shared memory camera bus.

    Supports both the CameraService API (PyQt6 VisionWorker)
    and the RealSenseCamera API (remote_draw_server).
    """

    def __init__(self, stale_threshold: float = _STALE_THRESHOLD):
        self._stale_threshold = stale_threshold
        self._shm_color: Optional[shared_memory.SharedMemory] = None
        self._shm_depth: Optional[shared_memory.SharedMemory] = None
        self._shm_meta:  Optional[shared_memory.SharedMemory] = None
        self._color_view: Optional[np.ndarray] = None
        self._depth_view: Optional[np.ndarray] = None
        self._connected  = False
        self._last_frame_ctr: int = -1
        self.depth_scale: float = 1.0

    # ------------------------------------------------------------------
    # Internal connect / disconnect
    # ------------------------------------------------------------------

    def _connect(self):
        if self._connected:
            return
        try:
            self._shm_color = shared_memory.SharedMemory(name=SHM_COLOR, create=False)
            self._shm_depth = shared_memory.SharedMemory(name=SHM_DEPTH, create=False)
            self._shm_meta  = shared_memory.SharedMemory(name=SHM_META,  create=False)

            self._color_view = np.ndarray(
                (FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8, buffer=self._shm_color.buf
            )
            self._depth_view = np.ndarray(
                (FRAME_HEIGHT, FRAME_WIDTH), dtype=np.uint16, buffer=self._shm_depth.buf
            )
            self.depth_scale = struct.unpack_from('d', self._shm_meta.buf, _OFF_DEPTH_SCALE)[0]
            self._connected = True
            print(f"[SharedCameraClient] Connected. depth_scale={self.depth_scale:.6f}")
        except FileNotFoundError:
            raise RuntimeError(
                "[SharedCameraClient] Shared memory not found. "
                "Is the camera server (run_camera_server.py) running?"
            )

    def _disconnect(self):
        if not self._connected:
            return
        self._color_view = None
        self._depth_view = None
        for shm in (self._shm_color, self._shm_depth, self._shm_meta):
            if shm is not None:
                try:
                    shm.close()
                except Exception:
                    pass
        self._shm_color = self._shm_depth = self._shm_meta = None
        self._connected = False

    def _is_server_running(self) -> bool:
        try:
            return bool(self._shm_meta.buf[_OFF_RUNNING])
        except Exception:
            return False

    # ------------------------------------------------------------------
    # CameraService interface (context manager + getFrames)
    # ------------------------------------------------------------------

    def start(self):
        """Also serves as RealSenseCamera.start()."""
        self._connect()

    def stop(self):
        """Also serves as RealSenseCamera.stop()."""
        self._disconnect()

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, *_):
        self._disconnect()

    def getFrames(self) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """
        CameraService-compatible method.
        Returns (success, color_bgr, depth_uint16).
        Raises RuntimeError if the server stopped unexpectedly.
        """
        if not self._connected:
            raise RuntimeError("SharedCameraClient is not connected.")

        if not self._is_server_running():
            raise RuntimeError("Camera server shut down.")

        ts = struct.unpack_from('d', self._shm_meta.buf, _OFF_TIMESTAMP)[0]
        if ts == 0.0:
            return False, None, None  # Server just started, no frame yet

        age = time.time() - ts
        if age > self._stale_threshold:
            return False, None, None  # Too old

        color = self._color_view.copy()
        depth = self._depth_view.copy()
        return True, color, depth

    # ------------------------------------------------------------------
    # RealSenseCamera interface (read)
    # ------------------------------------------------------------------

    def read(self) -> Optional[np.ndarray]:
        """
        RealSenseCamera-compatible method.
        Returns BGR color frame as ndarray, or None if no new frame.
        """
        if not self._connected:
            return None

        ts = struct.unpack_from('d', self._shm_meta.buf, _OFF_TIMESTAMP)[0]
        if ts == 0.0:
            return None

        ctr = struct.unpack_from('Q', self._shm_meta.buf, _OFF_FRAME_CTR)[0]
        if ctr == self._last_frame_ctr:
            return None  # No new frame since last read

        self._last_frame_ctr = ctr
        return self._color_view.copy()
