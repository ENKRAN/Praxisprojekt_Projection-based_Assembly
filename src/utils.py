import numpy as np

def pixelcoords_to_apriltagcoords(u, v, depth_frame, intrinsics, april_tag_pose):
    # Schritt 1: Erhalte die Tiefe genau am Kreiszentrum
    Z = depth_frame.get_distance(int(u), int(v))  # Tiefe in Metern

    if Z == 0:
        print("Keine Tiefeninformation an den angegebenen Pixelkoordinaten verfügbar.")
        return None

    # Schritt 2: Projiziere in 3D-Kamerakoordinaten (X, Y, Z)
    X = (u - intrinsics.ppx) * Z / intrinsics.fx
    Y = (v - intrinsics.ppy) * Z / intrinsics.fy
    P_c = np.array([X, Y, Z])
    
    # Debug: Ausgabe der Kamerakoordinaten (P_c)
    print(f"Kamerakoordinaten P_c: {P_c}")

    # Schritt 3: Bestimme die Transformation vom AprilTag zur Kamera
    R_ct, t_ct = april_tag_pose

    # Transformiere den Punkt in das AprilTag-Koordinatensystem
    P_t = R_ct.T @ (P_c - t_ct.flatten())

    print(f"AprilTag Position (t_ct): {t_ct.flatten()}")
    print(f"AprilTag Rotation (R_ct):\n{R_ct}")


    # Debug: Ausgabe des transformierten Punkts P_t
    print(f"3D-Koordinaten relativ zum AprilTag: {P_t}")

    return P_t
