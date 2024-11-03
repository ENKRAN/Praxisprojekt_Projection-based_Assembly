import subprocess
import os
import time
import pyautogui
import cv2
import numpy as np


def open_image_in_paint(image_path: str) -> None:
    """
    Open an image in MS Paint and create a new layer.

    :param image_path: The path to the image
    """
    # Check if the image exists
    if os.path.isfile(image_path):
        # MS Paint mit dem Bild öffnen
        process = subprocess.Popen(['mspaint', image_path])

        # Wartezeit, damit MS Paint vollständig geladen wird
        time.sleep(2)

        # Neue Ebene erstellen (Anpassung je nach Tastenkombination)
        pyautogui.hotkey('ctrl', 'shift', 'n')

        process.wait()

        print("MS paint is closed.")
    else:
        print(f"The image at {image_path} was not found.")


def analyze_multiple_drawings_with_advanced_filters(image_path: str, min_area: float = 5.0, min_width: int = 10, min_height: int = 10, scale_factor: float = 1.5):
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
        if hierarchy[0][i][3] == -1:  # -1 bedeutet keine übergeordnete Kontur
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
                
                # Konturkoordinaten speichern
                contour_coordinates = contour.reshape(-1, 2).tolist()
                
                # Zeichne die Bounding Box und den Mittelpunkt für die Verifikation
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Bounding Box in Grün
                cv2.drawMarker(image, (center_x, center_y), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=10, thickness=2)  # Mittelpunkt als Kreuz
                
                # Kontur als Linie zeichnen (optional, um die Form zu visualisieren)
                cv2.drawContours(image, [contour], -1, (255, 0, 0), 2)  # Kontur in Blau
                
                # Speichere die Details dieser Zeichnung in der Liste
                drawings.append({
                    "bounding_box": (x, y, w, h),
                    "center": (center_x, center_y),
                    "contour_coordinates": contour_coordinates,
                    "area": area
                })
    
    # Bild skalieren
    scaled_image = cv2.resize(image, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_LINEAR)
    
    # Zeige das skalierte Bild mit allen Bounding Boxes, Mittelpunkten und Konturen
    cv2.imshow("Mehrere Zeichnungen erkennen (vergrößert)", scaled_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    # Ausgabe der Anzahl und Details der Zeichnungen
    print(f"Anzahl gefundener Zeichnungen: {len(drawings)}")
    for i, drawing in enumerate(drawings):
        print(f"Zeichnung {i + 1}:")
        print(f"  Bounding Box: {drawing['bounding_box']}")
        print(f"  Mittelpunkt: {drawing['center']}")
        print(f"  Fläche: {drawing['area']}")
        print(f"  Anzahl Konturpunkte: {len(drawing['contour_coordinates'])}")
    
    # Rückgabe der Details aller Zeichnungen
    return drawings
