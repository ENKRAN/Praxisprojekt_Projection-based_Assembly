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

    Cvec = np.array([[X_c], 
                     [Y_c], 
                     [Z_c]])

    # check_pixel_to_camera_conversion(intrinsics, x_c, y_c, z_c)

    # Step 3: Transform the camera coordinates to AprilTag coordinates
    rmat = np.array(april_tag_pose[0])
    tvec = np.array(april_tag_pose[1])

    print(f"Rotation matrix: {rmat}")
    print(f"Translation vector: {tvec}")

    rinv = rmat.T
    
    Avec = np.dot(rinv, Cvec - tvec)

    print(f"Point in AprilTag coordinates: ({Avec[0]}, {Avec[1]}, {Avec[2]})")
    

    

    return None

def project_3d_to_2d(intrinsics, point_3d):
    fx = intrinsics.fx
    fy = intrinsics.fy
    cx = intrinsics.ppx
    cy = intrinsics.ppy

    x, y, z = point_3d
    u = int((x * fx) / z + cx)
    v = int((y * fy) / z + cy)

    return (u, v)