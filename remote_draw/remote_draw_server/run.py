import time
import cv2

from .config import AppConfig
from .remote_server import RemoteServer

# SharedCameraClient reads from the shared memory written by run_camera_server.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from app.hardware.shared_camera_client import SharedCameraClient

def main():
    cfg = AppConfig()

    server = RemoteServer(cfg)
    server.start()

    cam = SharedCameraClient()
    cam.start()
    print("SharedCameraClient connected to camera server")

    try:
        while True:
            frame = cam.read()
            if frame is not None:
                server.update_frame(frame)
            else:
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n[Exit] stopping…")
    finally:
        cam.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
