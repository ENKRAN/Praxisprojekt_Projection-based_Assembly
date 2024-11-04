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

def visualize_depth_image(depth_image):
    """
    Visualizes the depth image by normalizing it to a displayable range and using a color map.
    
    :param depth_image: Depth image as a numpy array
    """
    # Normalisiere das Tiefenbild auf einen Bereich von 0 bis 255 für die Anzeige
    depth_normalized = cv2.normalize(depth_image, None, 0, 255, cv2.NORM_MINMAX)
    depth_normalized = np.uint8(depth_normalized)
    
    # Wende eine Farbkarte an, um die Tiefe besser sichtbar zu machen (z.B. 'jet' oder 'plasma')
    depth_colormap = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_JET)
    
    # Zeige das Bild mit Matplotlib an
    plt.figure(figsize=(10, 6))
    plt.imshow(depth_colormap)
    plt.title("Visualized Depth Image")
    plt.axis('off')
    plt.show()

def draw_bounding_box_3d(img, bounding_box_points_3d, R_ct, tvec, camera_matrix, dist_coeffs):
    """
    Zeichnet die projizierten 3D-Bounding-Box-Eckpunkte auf das Bild und verbindet sie, um die Box zu visualisieren.

    :param img: Bild, auf das gezeichnet wird
    :param bounding_box_points_3d: Liste der 3D-Eckpunkte der Bounding Box relativ zum AprilTag
    :param R_ct: Rotationsmatrix von der Kamera zum Tag
    :param tvec: Translationsvektor von der Kamera zum Tag
    :param camera_matrix: Kameramatrix
    :param dist_coeffs: Verzerrungskoeffizienten der Kamera
    :return: Bild mit der projizierten Bounding Box
    """
    # Wandeln Sie die 3D-Eckpunkte in das benötigte Format für OpenCV um
    box_points_3d = np.array(bounding_box_points_3d, dtype=np.float32)

    # Projektion der 3D-Punkte auf 2D-Bildkoordinaten
    imgpts, _ = cv2.projectPoints(box_points_3d, R_ct, tvec, camera_matrix, dist_coeffs)
    
    # Konvertieren der projizierten Punkte in Ganzzahlen für die Darstellung
    imgpts = np.int32(imgpts).reshape(-1, 2)

    # Zeichnen der Linien, die die Eckpunkte verbinden
    img = cv2.line(img, tuple(imgpts[0]), tuple(imgpts[1]), (0, 255, 255), 2)  # obere Kante
    img = cv2.line(img, tuple(imgpts[1]), tuple(imgpts[2]), (0, 255, 255), 2)  # rechte Kante
    img = cv2.line(img, tuple(imgpts[2]), tuple(imgpts[3]), (0, 255, 255), 2)  # untere Kante
    img = cv2.line(img, tuple(imgpts[3]), tuple(imgpts[0]), (0, 255, 255), 2)  # linke Kante
    
    return img