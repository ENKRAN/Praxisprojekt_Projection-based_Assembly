import numpy as np
import cv2
import threading
from .image_processing import save_component_img, cam_2D_to_tag_3D
from .setup import initialize_system, get_calibration_data, update_windows
from .projection import setup_projector_window, project_image
from .utils import open_image_in_paint, show_depth_image
from .visualization import draw_axes, draw_tag_border_and_id
from .manual_creation import ManualCreater

def main() -> None:
    # Initialize the camera and AprilTag detector
    camera, apriltag_detector, camera_matrix, color_intrinsics, _ = initialize_system()

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
    window_thread.start()

    # Length of the axes in the visualization and the minimum distance to the tag in meters
    axis_length = apriltag_detector.tag_size
    min_distance = 0.15
    
    calibration_data_path = 'C:\\Users\\cenko\\Desktop\\Studium\\FH Aachen\\7. Semester\\Bachelor\\Projektor_Kamera_Kalibrierung\\calibration.yml'
    cam_K, cam_kc, proj_K, proj_kc, R, T = get_calibration_data(calibration_data_path)

    manual_creator = ManualCreater()
    manual_creator.create_manual(camera, apriltag_detector, min_distance, cam_K, cam_kc, axis_length, R, T, proj_K, proj_kc, projector_width, projector_height, projector_window_name, proj_image)

if __name__ == "__main__":
    main() 
