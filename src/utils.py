import numpy as np

def pixelcoords_to_apriltagcoords(u, v, depth_frame, intrinsics, april_tag_pose):
    print(f"Pixel coordinates: ({u}px, {v}px)")

    # Step 1: Get the camera depth sensor intrinsics
    Z_c = depth_frame.get_distance(int(u), int(v))  # Depth value in meters

    if Z_c == 0:
        print("Keine Tiefeninformation an den angegebenen Pixelkoordinaten verfügbar.")
        return None
    
    print(f"Distance to AprilTag: {Z_c}m")

    # Step 2: Convert the pixel coordinates to camera coordinates
    X_c = (int(u) - intrinsics["ppx"]) * Z_c / intrinsics["fx"]
    Y_c = (int(v) - intrinsics["ppy"]) * Z_c / intrinsics["fy"]

    print (f"Point in camera coordinates: ({X_c}, {Y_c}, {Z_c})")

    # check_pixel_to_camera_conversion(intrinsics, x_c, y_c, z_c)

    # Step 3: Transform the camera coordinates to AprilTag coordinates
    R_tc = np.array(april_tag_pose[0])
    t_tc = np.array(april_tag_pose[1])

    print(f"Rotation matrix: {R_tc}")
    print(f"Translation vector: {t_tc}")

    R_ct = R_tc.T
    t_ct = (-R_ct @ t_tc).flatten()

    

    return None


def check_pixel_to_camera_conversion(intrinsics, x_c, y_c, z_c):
    u_ = (intrinsics["fx"] * x_c / z_c) + intrinsics["ppx"]
    v_ = (intrinsics["fy"] * y_c / z_c) + intrinsics["ppy"]

    print(f"Reconstructed pixel coordinates: ({u_}px, {v_}px)")