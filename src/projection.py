import cv2
import sys
import numpy as np
from screeninfo import get_monitors
from typing import Tuple, List
import pyrealsense2 as rs
from .image_processing import save_component_img
import os
import glob

def setup_projector_window():
    # Get the second screen (projector)
    monitors = get_monitors()
    if len(monitors) < 2:
        print("Error: No second screen found. Please connect a second screen and try again.")
        sys.exit()

    # Get the second screen properties
    second_screen = monitors[1]
    screen_x = second_screen.x
    screen_y = second_screen.y
    projector_width = 1280
    projector_height = 720

    projector_window_name = 'Projector Window'

    """cv2.namedWindow(projector_window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(projector_window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.moveWindow(projector_window_name, screen_x, screen_y)  # Positioning on second screen"""

    return projector_window_name, projector_width, projector_height


def capture_calib_images(num_images, camera, calibration_images_dir):
    img_count = 0

    # Check if dir for calibration images exists
    if not os.path.exists(calibration_images_dir):
        os.makedirs(calibration_images_dir)

    while img_count < num_images:
        color_image, depth_image, depth_frame, _ = camera.get_frames()
        if color_image is None or depth_image is None or depth_frame is None:
            continue
        

        # Draw the count of images taken
        cv2.putText(color_image, f"Image {img_count}/{num_images}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Display the color image
        cv2.imshow("Color Image", color_image)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('s'):
            # Save the image
            img_filename = os.path.join(calibration_images_dir, f"calib_{img_count}.png")
            cv2.imwrite(img_filename, color_image)
            print(f"Image {img_count} saved.")
            img_count += 1
        elif key == ord('q'):
            break

    cv2.destroyAllWindows()

def calibrate_projector_camera(pattern_size, square_size, captured_images_dir):
    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    objp *= square_size

    object_points = []  # 3D Punkte
    image_points_camera = []  # 2D Kamerapunkte
    image_points_projector = []  # 2D Projektorpunkte



