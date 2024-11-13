import cv2
import time
import os
from .utils import pixelcoords_to_apriltagcoords
from typing import List, Dict, Tuple
import numpy as np

def save_component_img(frame, tag_id, save_dir="data/saved_images") -> Tuple[str, str]:
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