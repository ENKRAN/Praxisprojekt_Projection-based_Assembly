import cv2
import sys
import numpy as np
import glob
from screeninfo import get_monitors
from typing import Tuple

def setup_projector_window():
    # Get the second screen (projector)
    monitors = get_monitors()
    if len(monitors) < 2:
        print("Error: No second screen found. Please connect a second screen and try again.")
        sys.exit()

    # Get the second screen properties
    second_screen = monitors[1]
    screen_width = second_screen.width
    screen_height = second_screen.height
    screen_x = second_screen.x
    screen_y = second_screen.y

    projector_window_name = 'Projector Window'

    cv2.namedWindow(projector_window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(projector_window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.moveWindow(projector_window_name, screen_x, screen_y)  # Positioning on second screen

    return projector_window_name, screen_width, screen_height

def calibrate_projector_camera(square_size=0.06, camera_matrix=None, dist_coeffs=None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Vorbereiten der Objektpunkte (Projektor-Koordinaten)
    pattern_size = (9, 6)  # Anzahl der inneren Ecken im Schachbrett (Breite, Höhe)
    objp = np.zeros((pattern_size[0]*pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    objp *= square_size  # Skalieren auf die tatsächliche Größe der Quadrate

    objpoints = []  # 3D-Punkte im Projektorraum
    imgpoints = []  # 2D-Punkte im Kamerabild

    images = glob.glob('data/saved_images/projector_calib_images/*.jpg')
    print(f"Anzahl der zu verarbeitenden Bilder: {len(images)}")

    for fname in images:
        img = cv2.imread(fname)
        if img is None:
            print(f"Fehler: Bild konnte nicht geladen werden: {fname}")
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Finden der Ecken des Schachbretts
        ret, corners = cv2.findChessboardCorners(gray, pattern_size, None)

        if ret:
            objpoints.append(objp)
            imgpoints.append(corners)

            # Optional: Zeichnen der Ecken
            cv2.drawChessboardCorners(img, pattern_size, corners, ret)
            cv2.imshow('Ecken', img)
            cv2.waitKey(1000)
        else:
            print(f"Ecken nicht gefunden in Bild: {fname}")

    cv2.destroyAllWindows()

    print(f"Anzahl erkannter Muster: {len(objpoints)}")

    if len(objpoints) < 4:
        print("Fehler: Nicht genügend Muster erkannt für die Kalibrierung.")
        return None

    # Kalibrierung der Kamera (falls noch nicht erfolgt)
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, gray.shape[::-1], None, None)

    # Berechnen der Homographien für jedes Bild
    homographies = []
    for i in range(len(objpoints)):
        # Unverzerrte Bildpunkte berechnen
        imgpoints_undist = cv2.undistortPoints(imgpoints[i], camera_matrix, dist_coeffs)
        # Berechnen der Homographie zwischen Objektpunkten und Bildpunkten
        H, _ = cv2.findHomography(objpoints[i][:, :2], imgpoints_undist.reshape(-1, 2))
        if H is not None:
            homographies.append(H)
        else:
            print(f"Homographie konnte nicht berechnet werden für Bildindex {i}")

    if not homographies:
        print("Fehler: Keine Homographien berechnet. Kalibrierung fehlgeschlagen.")
        return None

    # Durchschnittliche Homographie berechnen
    H_proj = np.mean(homographies, axis=0)

    # Speichern der Homographie
    np.save('data/homography/homography_proj_cam.npy', H_proj)

    print("Kalibrierung abgeschlossen. Homographie gespeichert als 'homography_proj_cam.npy'.")

    return H_proj
