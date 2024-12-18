import numpy as np
import cv2
import threading
from .setup import initialize_system, get_calibration_data, update_windows
from .projection import setup_projector_window
from .manual_creation import ManualCreator
from PyQt5.QtWidgets import QApplication
import sys

def main() -> None:
    app = QApplication(sys.argv)


    # Setup the projector window
    global projector_window_name
    projector_window_name, projector_width, projector_height = setup_projector_window()

    # draw a red rectangle on the edges of the projector image
    proj_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)
    proj_image = cv2.rectangle(proj_image, (0, 0), (projector_width - 1, projector_height - 1), (0, 0, 255), 10)

    # Start the thread to update the windows
    window_thread = threading.Thread(
        target=update_windows,
        args=(projector_window_name,)
    )
    window_thread.daemon = True  # Damit der Thread beim Beenden des Programms ebenfalls beendet wird
    window_thread.start()
    
    calibration_data_path = 'data/projector_camera_calibration/calibration.yml'
    cam_K, cam_kc, proj_K, proj_kc, R, T = get_calibration_data(calibration_data_path)

    # Initialize the camera and AprilTag detector
    camera, apriltag_detector, _, _ = initialize_system(cam_K, color_width=1280, color_height=720, depth_width=1280, depth_heigth=720, fps=30, depth_intrinsics=False)

    manual_creator = ManualCreator(
        camera, 
        apriltag_detector,
        cam_K,
        cam_kc,
        projector_window_name,
        projector_width,
        projector_height,
        proj_image,
        R,
        T,
        proj_K,
        proj_kc
    )
    
    manual_creator.open_window()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 
