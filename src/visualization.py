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
    TODO: Maybe delete this function bcs no longer in use
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

def draw_bounding_box_and_drawing(img, drawing_img, drawing, R_ct, tvec, camera_matrix, dist_coeffs):
    """
    Visualisiert eine 3D-Bounding-Box im Bild und projiziert die Zeichnung ohne Hintergrund auf das Kamerabild.

    :param img: Bild, auf das gezeichnet werden soll
    :param drawing_img: Ursprungsbild mit den Zeichnungen
    :param drawing: Dictionary mit Details der Zeichnung
    :param R_ct: Rotationsmatrix von der Kamera zum Tag
    :param tvec: Translationsvektor von der Kamera zum Tag
    :param camera_matrix: Kameramatrix
    :param dist_coeffs: Verzerrungskoeffizienten
    :return: Bild mit gezeichneter 3D-Bounding-Box und projizierter Zeichnung ohne Hintergrund
    """
    # 3D-Punkte der Bounding-Box erhalten
    bounding_box_points_3d = drawing["bounding_box_points_3d"]

    # Konvertieren der 3D-Punkte der Bounding-Box in ein numpy-Array
    box_points_3d = np.array(bounding_box_points_3d, dtype=np.float32)

    # Projizieren der 3D-Bounding-Box-Punkte auf das 2D-Bild
    imgpts, _ = cv2.projectPoints(box_points_3d, R_ct, tvec, camera_matrix, dist_coeffs)

    # Konvertieren der Punkte in ganzzahlige Pixelkoordinaten für das Zeichnen
    imgpts_int = np.int32(imgpts).reshape(-1, 2)

    # Konvertieren der Punkte in float32 für die Homographie
    imgpts_float = np.float32(imgpts).reshape(-1, 2)

    # Zeichnen der Bounding-Box-Linien
    """if len(imgpts_int) >= 4:
        cv2.line(img, tuple(imgpts_int[0]), tuple(imgpts_int[1]), (0, 255, 255), 2)
        cv2.line(img, tuple(imgpts_int[1]), tuple(imgpts_int[2]), (0, 255, 255), 2)
        cv2.line(img, tuple(imgpts_int[2]), tuple(imgpts_int[3]), (0, 255, 255), 2)
        cv2.line(img, tuple(imgpts_int[3]), tuple(imgpts_int[0]), (0, 255, 255), 2)
    else:
        print("Warnung: Nicht genügend Punkte zum Zeichnen der Bounding-Box.")"""

    # ROI aus dem Ursprungsbild extrahieren
    x, y, w, h = drawing["bounding_box"]
    roi = drawing_img[y:y+h, x:x+w]

    # Erstellen der Maske basierend auf Pixelintensitäten
    # Konvertieren der ROI in Graustufen
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    # Erstellen einer binären Maske, wobei nicht schwarze Pixel auf 255 gesetzt werden
    _, mask = cv2.threshold(roi_gray, 10, 255, cv2.THRESH_BINARY)

    # Zeichnung mit Maske extrahieren
    drawing_extracted = cv2.bitwise_and(roi, roi, mask=mask)

    # Eckpunkte der ROI (Zeichnung)
    drawing_corners = np.array([[0, 0], [w - 1, 0], [w -1, h -1], [0, h -1]], dtype=np.float32)

    # Berechnen der Homographie zwischen Zeichnung und projizierter Bounding-Box
    if len(imgpts_float) >= 4:
        H, status = cv2.findHomography(drawing_corners, imgpts_float)

        # Projizieren der Zeichnung und der Maske auf das Kamerabild
        warped_drawing = cv2.warpPerspective(drawing_extracted, H, (img.shape[1], img.shape[0]))
        warped_mask = cv2.warpPerspective(mask, H, (img.shape[1], img.shape[0]))

        # Inverse Maske erstellen
        mask_inv = cv2.bitwise_not(warped_mask)

        # Sicherstellen, dass die Masken drei Kanäle haben
        if len(img.shape) == 3 and img.shape[2] == 3:
            warped_mask_color = cv2.merge([warped_mask, warped_mask, warped_mask])
            mask_inv_color = cv2.merge([mask_inv, mask_inv, mask_inv])
        else:
            warped_mask_color = warped_mask
            mask_inv_color = mask_inv

        # Hintergrund des Kamerabildes im Bereich der Zeichnung ausblenden
        img_bg = cv2.bitwise_and(img, img, mask=mask_inv)

        # Vordergrund der Zeichnung extrahieren
        img_fg = cv2.bitwise_and(warped_drawing, warped_drawing, mask=warped_mask)

        # Vordergrund und Hintergrund kombinieren
        img = cv2.add(img_bg, img_fg)
    else:
        print("Warnung: Nicht genügend Punkte zum Berechnen der Homographie.")

    return img

