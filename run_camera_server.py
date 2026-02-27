"""
Central Camera Server — run this FIRST before starting any other program.

    python run_camera_server.py

This process owns the Intel RealSense camera and writes every frame into
named shared memory. Both the PyQt6 app and the remote_draw_server can
then read frames simultaneously and independently via SharedCameraClient,
without ever opening the camera device themselves.
"""

from app.hardware.camera_server import run

if __name__ == "__main__":
    run()
