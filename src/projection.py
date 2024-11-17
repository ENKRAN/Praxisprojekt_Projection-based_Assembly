import cv2
import sys
import numpy as np
from screeninfo import get_monitors
from typing import Tuple
import pyrealsense2 as rs

def setup_projector_window():
    # Get the second screen (projector)
    monitors = get_monitors()
    if len(monitors) < 2:
        print("Error: No second screen found. Please connect a second screen and try again.")
        sys.exit()

    # Get the second screen properties
    second_screen = monitors[1]
    screen_x = second_screen.x
    screen_y = second_screen.y
    projector_width = 1280
    projector_height = 720

    projector_window_name = 'Projector Window'

    cv2.namedWindow(projector_window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(projector_window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.moveWindow(projector_window_name, screen_x, screen_y)  # Positioning on second screen

    return projector_window_name, projector_width, projector_height

def create_chessboard_image(pattern_size, square_size_px, image_size):
    cols, rows = pattern_size
    img_width, img_height = image_size
    chessboard_image = np.full((img_height, img_width), 255, dtype=np.uint8)

    # Berechnung der Startposition, um das Muster zentriert zu platzieren
    start_x = (img_width - cols * square_size_px) // 2
    start_y = (img_height - rows * square_size_px) // 2

    for i in range(rows):
        for j in range(cols):
            if (i + j) % 2 == 0:
                top_left_x = start_x + j * square_size_px
                top_left_y = start_y + i * square_size_px
                bottom_right_x = top_left_x + square_size_px
                bottom_right_y = top_left_y + square_size_px
                cv2.rectangle(
                    chessboard_image,
                    (top_left_x, top_left_y),
                    (bottom_right_x, bottom_right_y),
                    0,
                    -1
                )
    return chessboard_image

def analyze_chessboard_pattern(square_size=0.05, square_size_px=80, color_image=None, color_intrinsics=None, depth_frame=None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Vorbereitung der Objektpunkte (3D-Punkte im Weltkoordinatensystem)
    pattern_size = (9, 6)
    objp = np.zeros((pattern_size[0]*pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    objp *= square_size  # Skalieren auf die tatsächliche Größe in Metern

    # Listen zum Speichern der Punkte
    obj_points = []       # 3D-Punkte im Weltkoordinatensystem
    img_points = []       # 2D-Punkte im Kamerabild
    proj_img_points = []  # 2D-Punkte im Projektorbild

    # Anzahl der zu erfassenden Bilder
    num_images = 10
    captured_images = 0

    while captured_images < num_images:

        gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)

        # Suche nach Schachbrettmuster-Ecken
        ret_corners, corners = cv2.findChessboardCorners(gray, pattern_size, None)

        if ret_corners:
            # Ecken verfeinern
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_subpix = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)

            # 3D-Koordinaten der Ecken berechnen
            object_points = []
            for corner in corners_subpix:
                u, v = corner.ravel()
                depth = depth_frame.get_distance(int(u), int(v))
                if depth == 0:
                    continue  # Ungültiger Tiefenwert, überspringen
                point_3d = rs.rs2_deproject_pixel_to_point(color_intrinsics, [u, v], depth)
                object_points.append(point_3d)

            if len(object_points) != len(corners_subpix):
                print(f"Nicht alle Tiefenwerte gültig in Bild {captured_images + 1}, Bild wird übersprungen.")
                continue

            obj_points.append(np.array(object_points, dtype=np.float32))
            img_points.append(corners_subpix.reshape(-1, 2))

            # Projektorbildpunkte (bekannte 2D-Koordinaten im Projektorbild)
            proj_img = objp[:, :2] * square_size_px / square_size  # Skalierung auf Pixelgröße
            proj_img_points.append(proj_img)

            captured_images += 1
            print(f"Bild {captured_images}/{num_images} erfasst.")

            # Zeichne die erkannten Ecken
            cv2.drawChessboardCorners(color_image, pattern_size, corners_subpix, ret_corners)
            cv2.imshow('Erkannte Ecken', color_image)
            cv2.waitKey(500)  # Warte eine halbe Sekunde
        else:
            cv2.imshow('Erkannte Ecken', color_image)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    return obj_points, img_points, proj_img_points

