import numpy as np
import cv2
from utils import project_3d_to_2d

def test_tvec_difference(delta_t, my_pose_t, saved_image_path, intrinsics, apriltag_detector, pose_pixel):
    euclidean_distance = np.linalg.norm(delta_t)

    print(f"Differential translation vector: {delta_t}")
    print(f"Euclidean distance between the two translation vectors: {euclidean_distance:.6f} meters")

    depth_pixel = project_3d_to_2d(intrinsics, my_pose_t)

    print(f"Pfad zum gespeicherten Bild: '{saved_image_path}'")  

    image = cv2.imread(saved_image_path)
    cv2.circle(image, pose_pixel, 5, (0, 255, 255), -1)   
    cv2.circle(image, depth_pixel, 5, (255, 0, 255), -1) 

    # Definiere einen Bereich um die Punkte (z.B. 100x100 Pixel)
    x_min = min(pose_pixel[0], depth_pixel[0]) - 50
    y_min = min(pose_pixel[1], depth_pixel[1]) - 50
    x_max = max(pose_pixel[0], depth_pixel[0]) + 50
    y_max = max(pose_pixel[1], depth_pixel[1]) + 50

    # Stelle sicher, dass die Koordinaten innerhalb der Bildgrenzen liegen
    x_min = max(0, x_min)
    y_min = max(0, y_min)
    x_max = min(image.shape[1], x_max)
    y_max = min(image.shape[0], y_max)

    # Schneide den Bereich um die Punkte aus und vergrößere ihn
    zoomed_image = image[y_min:y_max, x_min:x_max]
    zoomed_image = cv2.resize(zoomed_image, (zoomed_image.shape[1] * 3, zoomed_image.shape[0] * 3))

    apriltag_detector.show_saved_detection_image(zoomed_image)