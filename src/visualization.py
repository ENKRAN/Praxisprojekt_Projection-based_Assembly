import numpy as np
import cv2

def draw_axes(img, rvec, tvec, camera_matrix, dist_coeffs, axis_length) -> np.ndarray:
    """
    Draws the 3D coordinate axes on the image.

    :param img: Image to draw on
    :param rvec: Rotation vector of the tag
    :param tvec: Translation vector of the tag
    :param camera_matrix: Camera matrix with intrinsics
    :param dist_coeffs: Distortion coefficients of the camera
    :param axis_length: Length of the axes to draw
    :return: Image with the coordinate axes drawn
    """
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

def draw_tag_border_and_id(frame, result) -> np.ndarray:
    """
    Draws the border and ID of the detected AprilTag.

    :param frame: Image to draw on
    :param result: Detected AprilTag result with corner positions and tag_id
    :return: Image with the tag border and ID drawn
    """
    # Get the corners of the tag
    corners = np.array(result.corners, dtype=np.int32).reshape((-1, 1, 2))
    
    # Draw the border of the tag
    frame = cv2.polylines(frame, [corners], isClosed=True, color=(0, 255, 0), thickness=2)

    # Label the tag with its ID
    center = tuple(corners[0][0])
    cv2.putText(frame, f"ID: {result.tag_id}", (center[0], center[1] - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return frame
