import numpy as np
import cv2
from typing import Any

def drawAxes(img: np.ndarray, R_ct: np.ndarray, tvec: np.ndarray, camera_matrix: np.ndarray, dist_coeffs: np.ndarray, axis_length: float) -> np.ndarray:
    """
    Draws the 3D axes on the detected tag.

    Args:
        img: Image to draw on
        R_ct: Rotation matrix from the camera frame to the tag frame
        tvec: Translation vector from the camera frame to the tag frame
        camera_matrix: Camera matrix
        dist_coeffs: Distortion coefficients
        axis_length: Length of the axes
    
    Returns:
        Image with the 3D axes drawn
    """
    # Convert rotation matrix to vector
    rvec, _ = cv2.Rodrigues(R_ct)

    # Define 3D points for the axes
    axis_points = np.float32([[0, 0, 0],            # Origin
                              [axis_length, 0, 0],  # x-axis
                              [0, axis_length, 0],  # y-axis
                              [0, 0, axis_length]]) # z-axis

    # Project 3D points to 2D image
    imgpts, _ = cv2.projectPoints(axis_points, rvec, tvec, camera_matrix, dist_coeffs)
    imgpts = np.int32(imgpts).reshape(-1, 2)

    # Draw axes
    origin = tuple(imgpts[0])
    img = cv2.arrowedLine(img, origin, tuple(imgpts[1]), (0, 0, 255), 2, tipLength=0.3)  # x (Red)
    img = cv2.arrowedLine(img, origin, tuple(imgpts[2]), (0, 255, 0), 2, tipLength=0.3)  # y (Green)
    img = cv2.arrowedLine(img, origin, tuple(imgpts[3]), (255, 0, 0), 2, tipLength=0.3)  # z (Blue)

    return img

def drawTagBorderAndId(img: np.ndarray, tag: Any) -> np.ndarray:
    """
    Draws the tag border and ID.

    Args:
        img: Image to draw on
        tag: Detected tag object
    
    Returns:
        Image with the tag border and ID drawn
    """
    corners = np.array(tag.corners, dtype=np.int32).reshape((-1, 1, 2))
    
    img = cv2.polylines(img, [corners], isClosed=True, color=(0, 255, 0), thickness=2)

    center = tuple(corners[0][0])
    cv2.putText(img, f"ID: {tag.tag_id}", (center[0], center[1] - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return img