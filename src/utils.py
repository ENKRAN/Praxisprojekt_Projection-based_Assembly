import cv2
import numpy as np

def pixel_to_tag_coords(pixel_point, rvec, tvec, camera_matrix, dist_coeffs):
    """
    Wandelt Bildkoordinaten (Pixelkoordinaten) in AprilTag-Koordinaten um.
    """
    # Pixelkoordinaten als 2D-Punkt
    pixel_point = np.array([[pixel_point]], dtype=np.float32)

    # Verwandle den 2D-Punkt in den 3D-Raum (Koordinaten relativ zum AprilTag)
    undistorted_point = cv2.undistortPoints(pixel_point, camera_matrix, dist_coeffs)

    # Wenn rvec eine 3x3-Matrix ist, verwende es als Rotationsmatrix, ansonsten verwandle es
    if rvec.shape == (3, 3):
        rotation_matrix = rvec
    else:
        rotation_matrix, _ = cv2.Rodrigues(rvec)

    # Überprüfe die Form von rotation_matrix (sollte 3x3 sein)
    assert rotation_matrix.shape == (3, 3), "Rotation matrix is not 3x3!"

    # Verwende die z-Komponente von tvec (die Tiefe des AprilTags) für die Projektion
    tag_depth = tvec[2]  # Tiefe des AprilTags

    # Nun setzen wir die z-Komponente des Punktes auf die Tiefe des AprilTags
    undistorted_point_3d = np.array([undistorted_point[0][0], undistorted_point[0][1], tag_depth])

    # Rückprojektion in den 3D-Raum (achte darauf, dass beide Punkte jetzt 3D sind)
    tag_point = np.dot(np.linalg.inv(rotation_matrix), (undistorted_point_3d - np.squeeze(tvec)))

    return tag_point
