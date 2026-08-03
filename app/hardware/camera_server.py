"""
Standalone Camera Server Process.

Captures frames from the Intel RealSense camera and writes them
continuously into named shared memory segments. Both the PyQt6 app
and the remote_draw_server can read frames independently via
SharedCameraClient without ever accessing the camera directly.

Usage:
    python run_camera_server.py

Shared Memory Layout:
    "cam_color"  : uint8  [HEIGHT, WIDTH, 3]  (BGR)
    "cam_depth"  : uint16 [HEIGHT, WIDTH]
    "cam_meta"   : bytes  64
        offset  0 : double  depth_scale
        offset  8 : double  last frame timestamp (time.time())
        offset 16 : uint64  frame counter (wraps)
        offset 24 : uint8   1 = server running, 0 = shutting down
"""

import signal
import struct
import time
from multiprocessing import shared_memory

import numpy as np
import pyrealsense2 as rs

# --- Constants (must match SharedCameraClient) ---
SHM_COLOR = "cam_color"
SHM_DEPTH = "cam_depth"
SHM_META  = "cam_meta"

FRAME_WIDTH    = 1280
FRAME_HEIGHT   = 720
FRAME_FPS      = 30
COLOR_SIZE     = FRAME_HEIGHT * FRAME_WIDTH * 3       # uint8
DEPTH_SIZE     = FRAME_HEIGHT * FRAME_WIDTH * 2       # uint16
META_SIZE      = 64

_OFF_DEPTH_SCALE = 0   # double (8 bytes)
_OFF_TIMESTAMP   = 8   # double (8 bytes)
_OFF_FRAME_CTR   = 16  # uint64 (8 bytes)
_OFF_RUNNING     = 24  # uint8  (1 byte)


def _cleanup_shm(name: str):
    """Silently unlink a leftover shared memory segment."""
    try:
        shm = shared_memory.SharedMemory(name=name, create=False)
        shm.close()
        shm.unlink()
    except FileNotFoundError:
        pass


def run():
    # --- Clean up any leftover segments from a previous crashed run ---
    for name in (SHM_COLOR, SHM_DEPTH, SHM_META):
        _cleanup_shm(name)

    # --- Create shared memory ---
    shm_color = shared_memory.SharedMemory(name=SHM_COLOR, create=True, size=COLOR_SIZE)
    shm_depth = shared_memory.SharedMemory(name=SHM_DEPTH, create=True, size=DEPTH_SIZE)
    shm_meta  = shared_memory.SharedMemory(name=SHM_META,  create=True, size=META_SIZE)

    # Numpy views directly into shared memory (zero-copy writes)
    color_buf = np.ndarray((FRAME_HEIGHT, FRAME_WIDTH, 3),  dtype=np.uint8,  buffer=shm_color.buf)
    depth_buf = np.ndarray((FRAME_HEIGHT, FRAME_WIDTH),     dtype=np.uint16, buffer=shm_depth.buf)

    # Mark server as running
    shm_meta.buf[_OFF_RUNNING] = 1

    # --- RealSense setup ---
    pipeline = rs.pipeline()
    config   = rs.config()
    config.enable_stream(rs.stream.color, FRAME_WIDTH, FRAME_HEIGHT, rs.format.bgr8, FRAME_FPS)
    config.enable_stream(rs.stream.depth, FRAME_WIDTH, FRAME_HEIGHT, rs.format.z16,  FRAME_FPS)
    profile  = pipeline.start(config)

    depth_sensor = profile.get_device().first_depth_sensor()
    depth_scale  = depth_sensor.get_depth_scale()
    struct.pack_into('d', shm_meta.buf, _OFF_DEPTH_SCALE, depth_scale)

    align = rs.align(rs.stream.color)

    # Warm-up: discard first few frames
    for _ in range(10):
        pipeline.wait_for_frames()

    print(f"[CameraServer] Running — depth_scale={depth_scale:.6f}")
    print(f"[CameraServer] Shared memory: {SHM_COLOR}, {SHM_DEPTH}, {SHM_META}")
    print(f"[CameraServer] Press Ctrl+C to stop.")

    frame_ctr = 0
    keep_running = True

    def _on_signal(sig, frame):
        nonlocal keep_running
        keep_running = False

    signal.signal(signal.SIGINT,  _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        while keep_running:
            try:
                frames = pipeline.wait_for_frames(timeout_ms=2000)
            except RuntimeError:
                print("[CameraServer] Frame timeout — retrying...")
                continue

            aligned      = align.process(frames)
            color_frame  = aligned.get_color_frame()
            depth_frame  = aligned.get_depth_frame()

            if not color_frame or not depth_frame:
                continue

            color_buf[:] = np.asanyarray(color_frame.get_data())
            depth_buf[:] = np.asanyarray(depth_frame.get_data())

            frame_ctr += 1
            struct.pack_into('d',  shm_meta.buf, _OFF_TIMESTAMP, time.time())
            struct.pack_into('Q',  shm_meta.buf, _OFF_FRAME_CTR, frame_ctr)

    finally:
        print("[CameraServer] Shutting down...")
        shm_meta.buf[_OFF_RUNNING] = 0
        pipeline.stop()
        for shm in (shm_color, shm_depth, shm_meta):
            shm.close()
            shm.unlink()
        print("[CameraServer] Stopped.")


if __name__ == "__main__":
    run()
