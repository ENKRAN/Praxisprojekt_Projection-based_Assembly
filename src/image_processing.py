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

def find_drawings_in_img(image_path: str, min_area: float = 1000.0, min_width: int = 50, min_height: int = 50, debug: bool = False) -> List[Dict]:
    """
    FIXME: Don't know if i need this function in future or not
    Find drawings in an image and return their details.

    :param image_path: The path to the image
    :param min_area: The minimum area of a drawing
    :param min_width: The minimum width of a drawing
    :param min_height: The minimum height of a drawing
    :return: A list of dictionaries containing the details of the drawings
    """
    image = cv2.imread(image_path)

    # Check if the image was loaded successfully
    if image is None:
        print(f"Error: Image not found at {image_path}")
        return []

    # Create a mask to filter out black areas
    non_black_mask = cv2.inRange(image, (1, 1, 1), (255, 255, 255))

    # Using closing to fill in the gaps in the drawings and connect the lines
    kernel = np.ones((10, 10), np.uint8)  # TODO: Test different kernel sizes
    closing = cv2.morphologyEx(non_black_mask, cv2.MORPH_CLOSE, kernel)

    # Find contours in the image
    contours, hierarchy = cv2.findContours(closing, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    drawings = []

    for i, contour in enumerate(contours):
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)

        # Filter out small contours
        if area >= min_area and w >= min_width and h >= min_height:
            # Calculate the center of the contour
            M = cv2.moments(contour)
            if M["m00"] != 0:
                center_x = int(M["m10"] / M["m00"])
                center_y = int(M["m01"] / M["m00"])
            else:
                center_x, center_y = 0, 0

            # Calculate the bounding box points
            top_left = (x, y)
            top_right = (x + w, y)
            bottom_left = (x, y + h)
            bottom_right = (x + w, y + h)
            bounding_box_points = [top_left, top_right, bottom_right, bottom_left]

            # Save the contour coordinates
            contour_coordinates = contour.reshape(-1, 2).tolist()

            # Optional: draw the bounding box, contour and center on the image
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.drawContours(image, [contour], -1, (255, 0, 0), 2)
            cv2.drawMarker(image, (center_x, center_y), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=10, thickness=2)

            # Save the details of the drawing
            drawings.append({
                "bounding_box": (x, y, w, h),
                "bounding_box_points": bounding_box_points,
                "center": (center_x, center_y),
                "contour_coordinates": contour_coordinates,
                "area": area
            })

    if debug:
        # Show the found drawings (optional)
        cv2.imshow("Found drawings", image)

        # Print drawing details (optional)
        print(f"Found drawings: {len(drawings)}")
        for i, drawing in enumerate(drawings):
            print(f"Drawing {i + 1}:")
            print(f"  Bounding Box: {drawing['bounding_box']}")
            print(f"  Bounding Box Points (2D): {drawing['bounding_box_points']}")
            print(f"  Center: {drawing['center']}")
            print(f"  Area: {drawing['area']}")
            print(f"  contour coordinate count: {len(drawing['contour_coordinates'])}")

    return drawings

def transform_bounding_boxes_to_3D(image_path: str, depth_frame, intrinsics, april_tag_pose) -> List[Dict]:
    """
    FIXME: Don't know if i need this function in future or not
    Transform the bounding boxes of drawings to 3D coordinates.

    :param image_path: The path to the image
    :param depth_frame: The depth frame
    :param intrinsics: The camera intrinsics
    :param april_tag_pose: The pose of the AprilTag
    :return: A list of dictionaries containing the details of the drawings with 3D coordinates
    """
    # Find the drawings in the image and get their details
    drawings = find_drawings_in_img(image_path, debug=True)
    
    for drawing in drawings:
        drawing["bounding_box_points_3d"] = []  # List to store the 3D coordinates
        
        # Convert each 2D point to 3D relative to the AprilTag
        for (u, v) in drawing["bounding_box_points"]:
            point_3d = pixelcoords_to_apriltagcoords(u, v, depth_frame, intrinsics, april_tag_pose)

            if point_3d is not None:
                drawing["bounding_box_points_3d"].append(point_3d)
            else:
                print(f"Warning: No depth value found for pixel coordinates ({u}, {v})")
    
    # Print the 3D coordinates of the bounding boxes for debugging
    for i, drawing in enumerate(drawings):
        print(f"Zeichnung {i + 1}:")
        print(f"  2D-Eckpunkte der Bounding Box: {drawing['bounding_box_points']}")
        print(f"  3D-Eckpunkte relativ zum AprilTag: {drawing['bounding_box_points_3d']}")
    
    return drawings

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