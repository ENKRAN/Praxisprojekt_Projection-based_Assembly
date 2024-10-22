import pupil_apriltags as apriltag
import cv2

# Beispielbild laden und vorbereiten
image =  cv2.imread("data/saved_images/", cv2.IMREAD_GRAYSCALE)

# Apriltag-Detector initialisieren
detector = apriltag.Detector()
detections = detector.detect(image)

# Überprüfen, ob Tags erkannt wurden
if len(detections) == 0:
    print("Keine Apriltags erkannt.")
else:
    print(f"{len(detections)} Apriltags erkannt.")
    for detection in detections:
        print(f"Tag ID: {detection.tag_id}")
        print(f"Zentrum: {detection.center}")
        print(f"Ecken: {detection.corners}")
