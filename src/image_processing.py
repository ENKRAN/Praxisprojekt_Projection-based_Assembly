import cv2
from typing import List, Dict, Tuple
import numpy as np

def extract_valid_image_points(image_with_drawings, depth_image, depth_scale) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extracts the valid image points (2D), depth values (meters) and colors (BGR) from the image with drawings using the depth image.

    :param image_with_drawings: The image with drawings
    :param depth_image: The depth image
    :param depth_scale: The depth scale
    :return: The u coordinates, v coordinates, depth values and colors
    """
    print(f"Depth image shape: {depth_image.shape}")
    print(f"Image with drawings shape: {image_with_drawings.shape}")

    # Check if the depth image and the image with drawings have the same resolution
    if depth_image.shape[:2] != image_with_drawings.shape[:2]:
        raise ValueError("The depth image and the image with drawings must have the same resolution")
    
    # Check if the image with drawings has an alpha channel and remove it (i don't think we need an alpha channel for now)
    if image_with_drawings.shape[2] == 4:
        image_with_drawings = cv2.cvtColor(image_with_drawings, cv2.COLOR_BGRA2BGR)

    # Extract all non-black pixels
    non_black_mask = np.any(image_with_drawings != 0, axis=-1)    

    # Extract the coordinates of the valid image points
    coords_yx = np.argwhere(non_black_mask)
    u_coords = coords_yx[:, 1]
    v_coords = coords_yx[:, 0]
    
    # Extract the depth values of the valid image points and scale them to meters
    depth_values_raw = depth_image[v_coords, u_coords]
    depth_values = depth_values_raw.astype(float) * depth_scale

    # Extract the colors of the valid image points
    colors_bgr = image_with_drawings[v_coords, u_coords, :]

    return u_coords, v_coords, depth_values, colors_bgr

def cam_2D_to_cam_3D(u_coords, v_coords, depth_values, cam_K) -> np.ndarray:
    """
    Converts multiple 2D image points to 3D camera coordinates.

    :param u_coords: The u coordinates of the image points
    :param v_coords: The v coordinates of the image points
    :param depth_values: The depth values of the image points
    :param cam_K: The camera matrix
    :return: The 3D camera coordinates
    """
    # Extract the camera intrinsics
    fx = cam_K[0, 0]
    fy = cam_K[1, 1]
    cx = cam_K[0, 2]
    cy = cam_K[1, 2]

    # Convert the 2D image points to 3D camera coordinates
    X = (u_coords - cx) * depth_values / fx
    Y = (v_coords - cy) * depth_values / fy
    Z = depth_values

    # Combine the 3D camera coordinates
    points_3d = np.column_stack((X, Y, Z))  # Nx3

    # Convert the 3D camera coordinates to homogeneous coordinates for further processing
    points_3d_hom = np.hstack([points_3d, np.ones((points_3d.shape[0], 1))])  # Nx4

    return points_3d, points_3d_hom 


def cam_2D_to_tag_3D(image_path: str, depth_image, depth_scale, cam_K, april_tag_pose) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert 2D image points to 3D tag coordinates.

    :param image_path: The path to the image with drawings
    :param depth_image: The depth image
    :param depth_scale: The depth scale
    :param cam_K: The camera matrix
    :param april_tag_pose: The AprilTag pose
    :return: The 3D tag coordinates, the homogeneous 3D tag coordinates and the colors
    """
    # Load the image with drawings
    image_with_drawings = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if image_with_drawings is None:
        raise FileNotFoundError(f"Image with drawing not found: {image_path}")

    # Extract valid image points, depth values and colors
    u_coords, v_coords, depth_values, colors_bgr = extract_valid_image_points(image_with_drawings, depth_image, depth_scale)

    # Convert 2D image points to 3D camera coordinates
    _, points_3d_cam_hom = cam_2D_to_cam_3D(u_coords, v_coords, depth_values, cam_K)

    # Extract the rotation and translation from the AprilTag pose
    R, t = april_tag_pose

    # Invert the rotation and translation
    R_inv = R.T
    t_inv = -R_inv @ t
    
    # Create the inverse transformation matrix
    T_inv = np.eye(4)
    T_inv[:3, :3] = R_inv
    T_inv[:3, 3] = t_inv

    # Convert the homogeneous 3D camera coordinates to homogeneous 3D tag coordinates
    points_3d_tag_hom = (T_inv @ points_3d_cam_hom.T).T

    # Normalize the 3D tag coordinates to get the cartesian 3D tag coordinates
    points_3d_tag = points_3d_tag_hom[:, :3] / points_3d_tag_hom[:, [3]]

    return points_3d_tag, points_3d_tag_hom, colors_bgr