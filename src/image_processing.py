import cv2
import time
import os
from .utils import pixelcoords_to_apriltagcoords
from typing import List, Dict

def save_component_img(frame, tag_id, save_dir="data/saved_images") -> str:
    """
    Save the component image to disk.

    :param frame: The image to save
    :param tag_id: The tag ID
    :param save_dir: The directory to save the image to
    :return: The path to the saved image
    """    
    # Create the directory if it does not exist
    os.makedirs(save_dir, exist_ok=True)

    # Generate a filename and timestamp
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"component_{tag_id}_{timestamp}.jpg"

    # Full path to the file
    filepath = os.path.join(save_dir, filename)

    # Save the image to disk
    cv2.imwrite(filepath, frame)
    print(f"Image saved at: {filepath}")

    return filepath, filename

def analyze_multiple_drawings(image_path: str, min_area: float = 5.0, min_width: int = 10, min_height: int = 10):
    # Bild laden
    image = cv2.imread(image_path)
    
    # Erstellen einer Maske für alle nicht-schwarzen Pixel
    non_black_mask = cv2.inRange(image, (1, 1, 1), (255, 255, 255))
    
    # Konturen und Hierarchie im Bild finden
    contours, hierarchy = cv2.findContours(non_black_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    
    # Liste, um Details aller gefilterten Zeichnungen zu speichern
    drawings = []
    
    # Jede Kontur in der Hierarchie analysieren
    for i, contour in enumerate(contours):
        # Nur äußere Konturen ohne übergeordnete Elemente berücksichtigen
        if hierarchy[0][i][3] == -1:
            # Konturfläche und Bounding Box prüfen
            area = cv2.contourArea(contour)
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter nach Fläche, Breite und Höhe der Bounding Box
            if area >= min_area and w >= min_width and h >= min_height:
                # Mittelpunkt der aktuellen Zeichnung berechnen
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    center_x = int(M["m10"] / M["m00"])
                    center_y = int(M["m01"] / M["m00"])
                else:
                    center_x, center_y = 0, 0
                
                # Berechnung der 2D-Eckpunkte der Bounding Box
                top_left = (x, y)
                top_right = (x + w, y)
                bottom_left = (x, y + h)
                bottom_right = (x + w, y + h)
                bounding_box_points = [top_left, top_right, bottom_right, bottom_left]
                
                # Speichern der Konturkoordinaten für spätere Referenz
                contour_coordinates = contour.reshape(-1, 2).tolist()
                
                # Zeichne die Bounding Box und den Mittelpunkt für die Verifikation
                cv2.circle(image, top_left, 5, (0, 255, 255), -1) # Eckpunkte in Gelb
                cv2.circle(image, top_right, 5, (0, 255, 255), -1)
                cv2.circle(image, bottom_left, 5, (0, 255, 255), -1)
                cv2.circle(image, bottom_right, 5, (0, 255, 255), -1)
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Bounding Box in Grün
                cv2.drawMarker(image, (center_x, center_y), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=10, thickness=2)  # Mittelpunkt als Kreuz
                cv2.drawContours(image, [contour], -1, (255, 0, 0), 2)  # Kontur in Blau
                
                # Speichere die Details dieser Zeichnung in der Liste
                drawings.append({
                    "bounding_box": (x, y, w, h),
                    "bounding_box_points": bounding_box_points,  # 2D-Eckpunkte
                    "center": (center_x, center_y),
                    "contour_coordinates": contour_coordinates,
                    "area": area
                })
    
    # Zeige das Bild mit allen Bounding Boxes, Mittelpunkten und Konturen
    cv2.imshow("Mehrere Zeichnungen erkennen", image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    # Ausgabe der Anzahl und Details der Zeichnungen
    print(f"Anzahl gefundener Zeichnungen: {len(drawings)}")
    for i, drawing in enumerate(drawings):
        print(f"Zeichnung {i + 1}:")
        print(f"  Bounding Box: {drawing['bounding_box']}")
        print(f"  Bounding Box Points (2D): {drawing['bounding_box_points']}")
        print(f"  Mittelpunkt: {drawing['center']}")
        print(f"  Fläche: {drawing['area']}")
        print(f"  Anzahl Konturpunkte: {len(drawing['contour_coordinates'])}")
    
    # Rückgabe der Details aller Zeichnungen
    return drawings

def analyze_drawings_and_transform_to_3d(image_path: str, depth_frame, intrinsics, april_tag_pose) -> List[Dict]:
    # Bild laden und Zeichnungen analysieren
    drawings = analyze_multiple_drawings(image_path)
    
    for drawing in drawings:
        # Liste, um die 3D-Koordinaten der Eckpunkte zu speichern
        drawing["bounding_box_points_3d"] = []
        
        # Iteriere über die Eckpunkte und transformiere sie in 3D
        for (u, v) in drawing["bounding_box_points"]:
            point_3d = pixelcoords_to_apriltagcoords(u, v, depth_frame, intrinsics, april_tag_pose)
            if point_3d is not None:
                drawing["bounding_box_points_3d"].append(point_3d)
            else:
                print(f"Warnung: Keine gültige 3D-Koordinate für Punkt ({u}, {v}) gefunden.")
    
    # Ausgabe der Ergebnisse für die Überprüfung
    for i, drawing in enumerate(drawings):
        print(f"Zeichnung {i + 1}:")
        print(f"  2D-Eckpunkte der Bounding Box: {drawing['bounding_box_points']}")
        print(f"  3D-Eckpunkte relativ zum AprilTag: {drawing['bounding_box_points_3d']}")
    
    return drawings