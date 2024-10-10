import pyrealsense2 as rs
import numpy as np
import cv2
from pupil_apriltags import Detector



# Funktion zum Zeichnen der 3D-Koordinatenachsen mit Pfeilen
def draw_axes(img, corners, rvec, tvec, camera_matrix, dist_coeffs, axis_length):
    # Definiere 3D-Punkte für die Achsen: Ursprung und Endpunkte (x, y, z)
    axis_points = np.float32([[0, 0, 0],            # Ursprung
                              [axis_length, 0, 0],  # x-Achse
                              [0, axis_length, 0],  # y-Achse
                              [0, 0, axis_length]]) # z-Achse

    # Projektion der 3D-Achsenpunkte in das 2D-Bild
    imgpts, _ = cv2.projectPoints(axis_points, rvec, tvec, camera_matrix, dist_coeffs)

    # Umwandeln in Integer-Pixelkoordinaten
    imgpts = np.int32(imgpts).reshape(-1, 2)

    # Zeichne die Achsen (x=rot, y=grün, z=blau) mit Pfeilspitzen
    origin = tuple(imgpts[0])
    img = cv2.arrowedLine(img, origin, tuple(imgpts[1]), (0, 0, 255), 2, tipLength=0.3)  # x-Achse (rot)
    img = cv2.arrowedLine(img, origin, tuple(imgpts[2]), (0, 255, 0), 2, tipLength=0.3)  # y-Achse (grün)
    img = cv2.arrowedLine(img, origin, tuple(imgpts[3]), (255, 0, 0), 2, tipLength=0.3)  # z-Achse (blau)
    return img

# Funktion zum Zeichnen der Umrandungen und der ID-Beschriftung
def draw_tag_border_and_id(frame, result):
    corners = np.array(result.corners, dtype=np.int32).reshape((-1, 1, 2))
    # Zeichne die Umrandung des Tags
    frame = cv2.polylines(frame, [corners], isClosed=True, color=(0, 255, 0), thickness=2)
    # Beschrifte den Tag mit der ID
    center = tuple(corners[0][0])
    cv2.putText(frame, f"ID: {result.tag_id}", (center[0], center[1] - 10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    return frame

def main():
    # RealSense-Kamera initialisieren
    pipeline = rs.pipeline()
    config = rs.config()

    # Wähle den Farbstream (RGB) aus
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    # Starte den Stream
    profile = pipeline.start(config)

    # Hole die intrinsics des Farbstreams
    color_sensor = profile.get_device().first_color_sensor()
    intrinsics = color_sensor.get_stream_profiles()[0].as_video_stream_profile().get_intrinsics()

    # Kameraintrinsische Parameter auslesen
    fx = intrinsics.fx
    fy = intrinsics.fy
    cx = intrinsics.ppx  # Optischer Mittelpunkt X
    cy = intrinsics.ppy  # Optischer Mittelpunkt Y
    dist_coeffs = np.array(intrinsics.coeffs)

    # Die Kameramatrix zusammenstellen
    camera_matrix = np.array([[fx, 0, cx],
                            [0, fy, cy],
                            [0, 0, 1]])

    # Größe des AprilTags in Metern (z.B. 4 cm)
    tag_size = 0.04

    # AprilTag-Detektor initialisieren
    detector = Detector(families="tagStandard41h12")

    # 3D-Achsenlängen für die Visualisierung (vergrößert)
    axis_length = tag_size * 2.0  # Achsen sind nun doppelt so lang wie das Tag

    # Z-Achsen-Richtungsfilter
    previous_z_direction = None  # Variable zum Speichern der vorherigen z-Achse

    try:
        while True:
            # Frame erfassen
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame:
                continue

            # In NumPy-Array konvertieren
            frame = np.asanyarray(color_frame.get_data())

            # In Graustufen konvertieren
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # AprilTags erkennen
            results = detector.detect(gray, estimate_tag_pose=True, camera_params=[fx, fy, cx, cy], tag_size=tag_size)

            # Erkennungen und Posen verarbeiten
            for result in results:
                # print(f"Tag ID: {result.tag_id}")

                # Translationsvektor (Position des Tags relativ zur Kamera)
                tvec = result.pose_t
                # Rotationsmatrix (Orientierung des Tags relativ zur Kamera)
                rvec = result.pose_R

                # Z-Richtungsstabilisierung:
                # Berechne die Richtung der z-Achse (tvec[2] ist die z-Komponente)
                current_z_direction = np.sign(tvec[2])  # Bestimme, ob z positiv oder negativ ist

                # Prüfe, ob die z-Achse plötzlich die Richtung geändert hat
                if previous_z_direction is not None and current_z_direction != previous_z_direction:
                    print("Achtung: Die z-Achse hat die Richtung geändert!")
                    # Option 1: Zwingen der z-Achse immer positiv zu sein
                    if tvec[2] < 0:
                        tvec = -tvec  # Invertiere den gesamten Translationsvektor

                # Aktualisiere die vorherige z-Richtung
                previous_z_direction = current_z_direction

                # Zeichne das Koordinatensystem (Achsen) auf das Bild
                frame = draw_axes(frame, result.corners, rvec, tvec, camera_matrix, dist_coeffs, axis_length)

                # Zeichne die Umrandungen und die ID des Tags
                frame = draw_tag_border_and_id(frame, result)

            # Bild anzeigen
            cv2.imshow('AprilTag-Erkennung mit Koordinatensystem und IDs', frame)
            if cv2.waitKey(1) == ord('q'):
                break
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 
