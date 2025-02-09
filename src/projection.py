import cv2
import sys
from screeninfo import get_monitors
import numpy as np
from typing import Any, Tuple

def setup_projector_window() -> Tuple[str, int, int]:
    """
    Set up the projector window on the third screen.

    :return: The name of the projector window, the width of the projector screen, and the height of the projector screen
    """
    # Get the third screen (projector)
    monitors = get_monitors()
    if len(monitors) < 3:
        print("Error: No third screen found. Please connect a third screen and try again.")
        sys.exit()

    # Get the third screen properties
    third_screen = monitors[2]
    screen_x = third_screen.x
    screen_y = third_screen.y
    projector_width = 1280
    projector_height = 720

    print(f"MY Projector screen: {projector_width}x{projector_height}")
    print(f"THEIR Projector screen: {third_screen.width}x{third_screen.height}")

    projector_window_name = 'Projector Window'

    cv2.namedWindow(projector_window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(projector_window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    cv2.moveWindow(projector_window_name, screen_x, screen_y)  # Positioning on third screen

    return projector_window_name, projector_width, projector_height

def project_image(img, points_3D_tag, valid_colors, R_cam_to_proj, tvec_cam_to_proj, R_tag_to_cam, tvec_tag_to_cam, proj_K, proj_kc, projector_width, projector_height) -> Any:
    """
    Project the image onto the projector screen.

    :param img: The image to project
    :param points_3D_tag: The 3D points of the AprilTag
    :param valid_colors: The colors of the AprilTag
    :param R_cam_to_proj: The rotation matrix from the camera to the projector
    :param tvec_cam_to_proj: The translation vector from the camera to the projector
    :param R_tag_to_cam: The rotation matrix from the AprilTag to the camera
    :param tvec_tag_to_cam: The translation vector from the AprilTag to the camera
    :param proj_K: The intrinsic matrix of the projector
    :param proj_kc: The distortion coefficients of the projector
    :param projector_width: The width of the projector screen
    :param projector_height: The height of the projector screen
    """
    # Calculate the rotation and translation from the AprilTag to the projector
    R_tag_to_proj = R_cam_to_proj @ R_tag_to_cam
    tvec_tag_to_proj = (R_cam_to_proj @ tvec_tag_to_cam + (tvec_cam_to_proj / 1000)).astype(np.float32)  # Convert to meters

    # Reshape the rotation matrix and translation vector for projection
    rvec_tag_to_proj, _ = cv2.Rodrigues(R_tag_to_proj.astype(np.float32))
    tvec_tag_to_proj = tvec_tag_to_proj.reshape(-1, 1)
    
    # Project the 3D points onto the projector screen
    proj_imgpts, _ = cv2.projectPoints(points_3D_tag, rvec_tag_to_proj, tvec_tag_to_proj, proj_K.astype(np.float32), proj_kc.astype(np.float32))

    # Create an empty image for the projector
    img = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)

    # Convert the points into integer pixel coordinates
    proj_imgpts = np.int32(proj_imgpts).reshape(-1, 2)

    # Filter out the points that are out of bounds
    in_bounds_mask = (
        (proj_imgpts[:, 0] >= 0) & (proj_imgpts[:, 0] < projector_width) &
        (proj_imgpts[:, 1] >= 0) & (proj_imgpts[:, 1] < projector_height)
    )

    # Draw the colors on the projector screen
    valid_pixel_coords = proj_imgpts[in_bounds_mask]
    valid_colors_in_bounds = valid_colors[in_bounds_mask]
    img[valid_pixel_coords[:, 1], valid_pixel_coords[:, 0]] = valid_colors_in_bounds

    # cv2.imshow("Projector debug", img)

    # Draw a border around the projector screen
    img = cv2.rectangle(img, (0, 0), (projector_width - 1, projector_height - 1), (0, 255, 0), 10)

    return img
