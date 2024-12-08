import cv2
from typing import List, Dict, Tuple
import numpy as np

def extract_valid_image_points(image_with_drawings, depth_image, depth_scale) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extracts the valid image points (2D), depth values (meters) and colors (RGB) from the image with drawings using the depth image.

    :param image_with_drawings: The image with the drawings (RGB)
    :param depth_image: The depth image (millimeters)
    :param depth_scale: The depth scale of the depth sensor
    :return: The valid image points, depth values and colors
    """
    # Extract all non-black pixels
    non_black_mask = np.any(image_with_drawings != [0, 0, 0], axis=-1)                
    
    # Get the coordinates and colors of the non-black pixels
    non_black_coords = np.column_stack(np.nonzero(non_black_mask))
    non_black_colors = image_with_drawings[non_black_mask]

    # Scale the depth_image to meters and get the depth values of the non-black pixels
    depth_image = depth_image * depth_scale
    depth_values = depth_image[non_black_coords[:, 0], non_black_coords[:, 1]]
    

    # Filter out the invalid depth values
    valid_depth_mask = (depth_values > 0) & (~np.isnan(depth_values))

    # Save the valid coordinates, colors and depth values
    valid_coords = non_black_coords[valid_depth_mask]
    valid_colors = non_black_colors[valid_depth_mask]
    valid_depths = depth_values[valid_depth_mask]

    # Store the valid image points in the format (u, v)
    image_points = valid_coords[:, [1, 0]].astype(np.float32).reshape(-1, 1, 2)  # (u, v)

    return image_points, valid_depths, valid_colors

def cam_2D_to_cam_3D(image_points_2D, depth_values, cam_K, cam_kc) -> np.ndarray:
    """
    Converts multiple 2D image points to 3D camera coordinates.

    :param image_points_2D: The 2D image points
    :param depth_values: The depth values
    :param cam_K: The camera matrix
    :param cam_kc: The distortion coefficients
    :return: The 3D camera coordinates
    """
    # Undistort Points
    undistorted_points = cv2.undistortPoints(image_points_2D, cam_K, cam_kc)

    # Calculate 3D coordinates
    x = undistorted_points[:, 0, 0]
    y = undistorted_points[:, 0, 1]
    Z_c = depth_values  # Depth values in meters

    # Calculate X, Y, Z
    X_c = x * Z_c
    Y_c = y * Z_c

    # Stack the 3D points
    points_3d_camera = np.vstack((X_c, Y_c, Z_c)).T  # (N, 3)

    return points_3d_camera


def cam_2D_to_tag_3D(image_path: str, depth_image, depth_scale, cam_K, cam_kc, april_tag_pose) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert 2D image points to 3D tag coordinates.

    :param image_path: The path to the image with drawings
    :param depth_image: The depth image
    :param depth_scale: The depth scale
    :param cam_K: The camera matrix
    :param cam_kc: The distortion coefficients
    :param april_tag_pose: The pose of the AprilTag
    :return: The 3D tag coordinates and valid colors
    """
    # Load the image with drawings
    image_with_drawings = cv2.imread(image_path)

    # Extract valid image points, depth values and colors
    image_points_2D, valid_depths, valid_colors = extract_valid_image_points(image_with_drawings, depth_image, depth_scale)

    # Convert 2D image points to 3D camera coordinates
    points_3d_camera = cam_2D_to_cam_3D(image_points_2D, valid_depths, cam_K, cam_kc)

    # Transform 3D camera coordinates to 3D tag coordinates
    R = april_tag_pose[0]
    t = april_tag_pose[1]

    points_3d_tag = np.dot(R.T, points_3d_camera.T - t).T

    return points_3d_tag, valid_colors