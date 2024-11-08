import numpy as np
import cv2
import matplotlib.pyplot as plt
from typing import Any

def draw_axes(img, R_ct, tvec, camera_matrix, dist_coeffs, axis_length) -> Any:
    """
    Draws the 3D coordinate axes on the image.

    :param img: Image to draw on
    :param R_ct: Rotation matrix from the camera to the tag
    :param tvec: Translation vector from the camera to the tag
    :param camera_matrix: Camera matrix
    :param dist_coeffs: Distortion coefficients
    :param axis_length: Length of the axes in the visualization
    :return: Image with the 3D coordinate axes drawn
    """
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

def draw_tag_border_and_id(frame, result) -> Any:
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

def draw_bounding_box_and_drawing(img, drawing_img, drawing, R_ct, tvec, camera_matrix, dist_coeffs) -> Any:
    """
    Visualizes the drawing on the camera image by projecting the drawing onto the image using a homography.

    :param img: Camera image
    :param drawing_img: Drawing image
    :param drawing: Drawing data with bounding box points and coordinates
    :param R_ct: Rotation matrix from the camera to the tag
    :param tvec: Translation vector from the camera to the tag
    :param camera_matrix: Camera matrix
    :param dist_coeffs: Distortion coefficients
    :return: Image with the drawing projected onto it
    """
    # Get the 3D points of the corners of the bounding box
    bounding_box_points_3d = drawing["bounding_box_points_3d"]

    # print(f'bounding_box_points_3d: {bounding_box_points_3d}')

    # Convert the points to a numpy array for opencv
    box_points_3d = np.array(bounding_box_points_3d, dtype=np.float32)

    # Project the 3D bounding box points onto the 2D image with correct perspective
    imgpts, _ = cv2.projectPoints(box_points_3d, R_ct, tvec, camera_matrix, dist_coeffs)

    # Convert the points into integer pixel coordinates for drawing
    imgpts_int = np.int32(imgpts).reshape(-1, 2)

    # Convert the points into float pixel coordinates for homography
    imgpts_float = np.float32(imgpts).reshape(-1, 2)

    # Draw the bounding box on the image (for debugging)
    """if len(imgpts_int) >= 4:
        cv2.line(img, tuple(imgpts_int[0]), tuple(imgpts_int[1]), (0, 255, 255), 2)
        cv2.line(img, tuple(imgpts_int[1]), tuple(imgpts_int[2]), (0, 255, 255), 2)
        cv2.line(img, tuple(imgpts_int[2]), tuple(imgpts_int[3]), (0, 255, 255), 2)
        cv2.line(img, tuple(imgpts_int[3]), tuple(imgpts_int[0]), (0, 255, 255), 2)
    else:
        print("Warnung: Nicht genügend Punkte zum Zeichnen der Bounding-Box.")"""

    # Extract the ROI of the drawing
    x, y, w, h = drawing["bounding_box"]
    roi = drawing_img[y:y+h, x:x+w]

    # Create the mask based on the pixel intensities
    # Convert the ROI to grayscale
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    # Create a binary mask where pixels with a intensity greater than 10 are set to 255 (white) 
    _, mask = cv2.threshold(roi_gray, 10, 255, cv2.THRESH_BINARY)

    # Extract the drawing based on the mask
    drawing_extracted = cv2.bitwise_and(roi, roi, mask=mask)

    # Corner points of the ROI (drawing)
    drawing_corners = np.array([[0, 0], [w - 1, 0], [w -1, h -1], [0, h -1]], dtype=np.float32)

    # Calculate the homography matrix between the Corners of the ROI and the projected 3D points of the bounding box
    if len(imgpts_float) >= 4:
        H, status = cv2.findHomography(drawing_corners, imgpts_float)

        # Project the mask and drawing onto the camera image
        warped_drawing = cv2.warpPerspective(drawing_extracted, H, (img.shape[1], img.shape[0]))
        warped_mask = cv2.warpPerspective(mask, H, (img.shape[1], img.shape[0]))

        # Create inverse mask for the drawing
        mask_inv = cv2.bitwise_not(warped_mask)

        # Check if the image has 3 channels (RGB) and create a mask with 3 channels
        if len(img.shape) == 3 and img.shape[2] == 3:
            warped_mask_color = cv2.merge([warped_mask, warped_mask, warped_mask])
            mask_inv_color = cv2.merge([mask_inv, mask_inv, mask_inv])
        else:
            warped_mask_color = warped_mask
            mask_inv_color = mask_inv

        # Hide the background of the camera image in the ROI
        img_bg = cv2.bitwise_and(img, img, mask=mask_inv)

        # Extract the foreground of the drawing
        img_fg = cv2.bitwise_and(warped_drawing, warped_drawing, mask=warped_mask)

        # Combine the foreground and background to get the final image
        img = cv2.add(img_bg, img_fg)
    else:
        print("Warning: Not enough points to draw the drawing.")

    return img

