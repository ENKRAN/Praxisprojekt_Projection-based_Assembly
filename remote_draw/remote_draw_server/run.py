import time
import cv2

from .config import AppConfig
from .camera_realsense import RealSenseCamera
from .remote_server import RemoteServer

def main():
    cfg = AppConfig()

    server = RemoteServer(cfg)
    server.start()

    cam = RealSenseCamera(cfg.width, cfg.height, cfg.fps)
    cam.start()
    print("Camera RealSense started")

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
