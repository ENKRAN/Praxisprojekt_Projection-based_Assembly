import pyrealsense2 as rs
import numpy as np
from src.setup import get_calibration_data
from PyQt6.QtWidgets import QApplication, QMainWindow
import sys

def numpy_to_rs_intrinsics(K, dist_coeffs, width, height):
    intrin = rs.intrinsics()
    
    intrin.width = int(width)
    intrin.height = int(height)
    
    intrin.ppx = float(K[0, 2])
    intrin.ppy = float(K[1, 2])
    intrin.fx = float(K[0, 0])
    intrin.fy = float(K[1, 1])
    
    if dist_coeffs is not None:
        if isinstance(dist_coeffs, np.ndarray):
            coeffs_list = dist_coeffs.flatten().tolist()
        else:
            coeffs_list = list(dist_coeffs)
        
        coeffs_list = [float(c) for c in coeffs_list]

        if len(coeffs_list) < 5:
            coeffs_list += [0.0] * (5 - len(coeffs_list))
        elif len(coeffs_list) > 5:
            coeffs_list = coeffs_list[:5]

        intrin.model = rs.distortion.brown_conrady
        intrin.coeffs = coeffs_list
    else:
        intrin.model = rs.distortion.none
        intrin.coeffs = [0.0, 0.0, 0.0, 0.0, 0.0]

    return intrin

def findTagPlaneIntersect(u, v, cam_intrinsics, tag_to_cam_filtered):
    ray_cam_raw = rs.rs2_deproject_pixel_to_point(cam_intrinsics, [u, v], 1.0)
    ray_cam = np.array([ray_cam_raw[0], ray_cam_raw[1], ray_cam_raw[2]])

    try:
        cam_to_tag_filtered = np.linalg.inv(tag_to_cam_filtered) 
    except np.linalg.LinAlgError:
        return None
    
    ray_origin_from_tag = cam_to_tag_filtered[:3, 3]

    rotation_inv = cam_to_tag_filtered[:3, :3]
    ray_dir_from_tag = rotation_inv @ ray_cam

    # Check if ray is parallel to the tag plane (z=0)
    if abs(ray_dir_from_tag[2]) < 1e-6:
        return None
    
    t = -ray_origin_from_tag[2] / ray_dir_from_tag[2]

    if t < 0:
        return None
    
    intersect_point = ray_origin_from_tag + t * ray_dir_from_tag

    print(f"Intersect Point: {intersect_point}")

    return intersect_point[:2]

if __name__ == "__main__":
    # Example usage
    u, v = 320, 240  # Example user units (pixel coordinates)

    calibration_data_path = 'data/projector_camera_calibration/calibration.yml'
    cam_K, cam_kc, proj_K, proj_kc, R, T = get_calibration_data(calibration_data_path)

    cam_intrinsics = numpy_to_rs_intrinsics(cam_K, cam_kc, width=1280, height=720)

    dummy_tag_to_cam = np.array([[0.866, -0.5, 0, 0.1],
                                 [0.5, 0.866, 0, 0.2],
                                 [0, 0, 1, 0.5],
                                 [0, 0, 0, 1]])

    tag_plane_intersect_point = findTagPlaneIntersect(u, v, cam_intrinsics, dummy_tag_to_cam)

    x_mm = tag_plane_intersect_point[0] * 1000
    y_mm = tag_plane_intersect_point[1] * 1000

    print(f"Tag Plane Intersection in mm: x={x_mm}, y={y_mm}")

    

    test_svg_path = 'test.svg'
     



