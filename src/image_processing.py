import cv2
import time
import os
from .utils import pixelcoords_to_apriltagcoords
from typing import List, Dict, Tuple
import numpy as np
from scipy.interpolate import griddata

def save_component_img(frame, tag_id=None, save_dir="data/saved_images") -> Tuple[str, str]:
    """
    Save the component image to disk.

    :param frame: The image to save
    :param tag_id: The tag ID
    :param save_dir: The directory to save the image to
    :return: The path to the saved image
    """    
    # Create the directory if it does not exist
    os.makedirs(save_dir, exist_ok=True)

    # Generate a filename and timestamp
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"component_{tag_id}_{timestamp}.jpg"

    # Full path to the file
    filepath = os.path.join(save_dir, filename)

    # Save the image to disk
    cv2.imwrite(filepath, frame)
    print(f"Image saved at: {filepath}")

    return filepath, filename

def extract_valid_image_points(image_with_drawings, depth_image, depth_scale):
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

def extract_valid_image_points_2(image_with_drawings, depth_image, depth_scale):
    # Extrahieren der Nicht-Schwarz-Pixel
    non_black_mask = np.any(image_with_drawings != [0, 0, 0], axis=-1)
    non_black_coords = np.column_stack(np.nonzero(non_black_mask))
    non_black_colors = image_with_drawings[non_black_mask]

    # Tiefenwerte der Nicht-Schwarz-Pixel extrahieren
    depth_values = depth_image[non_black_coords[:, 0], non_black_coords[:, 1]] * depth_scale

    # Erstellen einer Tiefenkarte der gezeichneten Punkte
    depth_map = np.zeros_like(depth_image, dtype=np.float32)
    depth_map[non_black_coords[:, 0], non_black_coords[:, 1]] = depth_values

    # Maskieren der fehlenden oder ungültigen Tiefenwerte
    depth_mask = (depth_map > 0) & (~np.isnan(depth_map))

    return non_black_coords, non_black_colors, depth_map, depth_mask

def interpolate_depth_map(depth_map, depth_mask):
    # Extrahieren der bekannten Tiefenwerte
    known_coords = np.argwhere(depth_mask)
    known_depths = depth_map[depth_mask]

    # Erstellen eines Gitters für die Interpolation
    grid_x, grid_y = np.mgrid[0:depth_map.shape[0], 0:depth_map.shape[1]]

    # Interpolation durchführen
    interpolated_depth_map = griddata(
        known_coords,
        known_depths,
        (grid_x, grid_y),
        method='linear',
        fill_value=0
    )

    return interpolated_depth_map

def cam_2D_to_cam_3D(non_black_coords, interpolated_depth_map, cam_K, cam_kc):

    # Extrahieren der Tiefenwerte von der interpolierten Tiefenkarte
    depth_values = interpolated_depth_map[non_black_coords[:, 0], non_black_coords[:, 1]]

    # Bildpunkte erstellen
    image_points = non_black_coords[:, [1, 0]].astype(np.float32).reshape(-1, 1, 2)

    # Undistort Points
    undistorted_points = cv2.undistortPoints(image_points, cam_K, cam_kc)

    # Rückprojektion in 3D
    x = undistorted_points[:, 0, 0]
    y = undistorted_points[:, 0, 1]
    Z_c = depth_values  # Verwenden der interpolierten Tiefenwerte

    X_c = x * Z_c
    Y_c = y * Z_c

    points_3d_camera = np.vstack((X_c, Y_c, Z_c)).T  # (N, 3)

    return points_3d_camera


def cam_2D_to_tag_3D(image_path: str, depth_image, depth_scale, cam_K, cam_kc, april_tag_pose):
    image_with_drawings = cv2.imread(image_path)

    # Schritt 1: Extrahieren der Bildpunkte und Erstellung der Tiefenkarte
    image_points, valid_colors, depth_map, depth_mask = extract_valid_image_points_2(image_with_drawings, depth_image, depth_scale)

    # Schritt 2: Interpolation der Tiefenkarte
    interpolated_depth_map = interpolate_depth_map(depth_map, depth_mask)

    # Schritt 3: Rückprojektion in 3D-Kamerakoordinaten
    points_3d_camera = cam_2D_to_cam_3D(image_points, interpolated_depth_map, cam_K, cam_kc)

    R = april_tag_pose[0]
    t = april_tag_pose[1]

    points_3d_tag = np.dot(R.T, points_3d_camera.T - t).T

    return points_3d_tag, valid_colors