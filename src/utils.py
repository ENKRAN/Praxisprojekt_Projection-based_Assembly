import numpy as np
from typing import Tuple

def pixelcoords_to_apriltagcoords(u, v, depth_frame, intrinsics, april_tag_pose) -> np.ndarray:
    """
    Convert pixel coordinates to AprilTag coordinates

    :param u: Pixel coordinate in x-direction
    :param v: Pixel coordinate in y-direction
    :param depth_frame: Depth frame from the camera
    :param intrinsics: Camera intrinsics
    :param april_tag_pose: Pose of the AprilTag
    :return: AprilTag coordinates
    """
    print(f"Pixel coordinates: ({u}px, {v}px)")

    # Step 1: Get the camera depth sensor intrinsics
    Z_c = depth_frame.get_distance(int(u), int(v))  # Depth value in meters

    if Z_c == 0:
        print("No depth value found")
        return None
    
    print(f"Distance to AprilTag: {Z_c}m")

    # Step 2: Convert the pixel coordinates to camera coordinates
    X_c = (int(u) - intrinsics["ppx"]) * Z_c / intrinsics["fx"]
    Y_c = (int(v) - intrinsics["ppy"]) * Z_c / intrinsics["fy"]

    print (f"Point in camera coordinates: ({X_c}, {Y_c}, {Z_c})")

    Cvec = np.array([[X_c], 
                     [Y_c], 
                     [Z_c]])

    # Step 3: Transform the camera coordinates to AprilTag coordinates
    rmat = np.array(april_tag_pose[0])
    tvec = np.array(april_tag_pose[1])

    print(f"Rotation matrix: {rmat}")
    print(f"Translation vector: {tvec}")

    # Inverse of the rotation matrix
    rinv = rmat.T

    # Calculate the AprilTag coordinates
    Avec = np.dot(rinv, Cvec - tvec)
    
    return Avec

def project_3d_to_2d(intrinsics, point_3d) -> Tuple[int, int]:
    """
    Project a 3D point to a 2D point    
    ### FIXME: Maybe change it so that it uses the RealSense method for the projection ###

    :param intrinsics: Camera intrinsics
    :param point_3d: 3D point
    :return: 2D point
    """
    fx = intrinsics.fx
    fy = intrinsics.fy
    cx = intrinsics.ppx
    cy = intrinsics.ppy

    x, y, z = point_3d
    u = int((x * fx) / z + cx)
    v = int((y * fy) / z + cy)

    return (u, v)