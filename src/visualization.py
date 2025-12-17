import numpy as np
import cv2
from typing import Any

def drawAxes(img, R_ct, tvec, camera_matrix, dist_coeffs, axis_length) -> Any:
    """
    Draws the 3D axes on the apriltag.

    :param img: Image to draw on
    :param R_ct: Rotation matrix from the camera frame to the tag frame
    :param tvec: Translation vector from the camera frame to the tag frame
    :param camera_matrix: Camera matrix
    :param dist_coeffs: Distortion coefficients
    :param axis_length: Length of the axes
    :return: Image with the 3D axes drawn
    """
    # Convert the rotation matrix to a rotation vector
    rvec, _ = cv2.Rodrigues(R_ct)

    # Define 3D points for the axes: Origin and end points for x, y, z axes
    axis_points = np.float32([[0, 0, 0],            # Origin
                              [axis_length, 0, 0],  # x-axis
                              [0, axis_length, 0],  # y-axis
                              [0, 0, axis_length]]) # z-axis

    # Project the 3D axis points onto the 2D image
    imgpts, _ = cv2.projectPoints(axis_points, rvec, tvec, camera_matrix, dist_coeffs)

    # Convert the points into integer pixel coordinates
    imgpts = np.int32(imgpts).reshape(-1, 2)

    # Draw the axes (x=red, y=green, z=blue) with arrow tips
    origin = tuple(imgpts[0])
    img = cv2.arrowedLine(img, origin, tuple(imgpts[1]), (0, 0, 255), 2, tipLength=0.3)  # x-axis (red)
    img = cv2.arrowedLine(img, origin, tuple(imgpts[2]), (0, 255, 0), 2, tipLength=0.3)  # y-axis (green)
    img = cv2.arrowedLine(img, origin, tuple(imgpts[3]), (255, 0, 0), 2, tipLength=0.3)  # z-axis (blue)

    return img

def drawTagBorderAndId(img, tag) -> Any:
    """
    Draws the border of the detected tag and its ID on the image.

    :param img: Image to draw on
    :param tag: Detected tag object
    :return: Image with the tag border and ID drawn
    """
    # Get the corners of the tag
    corners = np.array(tag.corners, dtype=np.int32).reshape((-1, 1, 2))
    
    # Draw the border of the tag
    img = cv2.polylines(img, [corners], isClosed=True, color=(0, 255, 0), thickness=2)

    # Label the tag with its ID
    center = tuple(corners[0][0])
    cv2.putText(img, f"ID: {tag.tag_id}", (center[0], center[1] - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return img



