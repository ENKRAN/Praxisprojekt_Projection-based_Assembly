import numpy as np
from typing import Tuple
from .camera import Camera
import subprocess
import os
import time
import pyautogui
import cv2

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

    # Step 1: Get the camera depth sensor value
    Z_c = depth_frame.get_distance(int(u), int(v))  # Depth value in meters

    if Z_c == 0:
        print("No depth value found")
        return None
    
    # print(f"Distance to Point: {Z_c}m")

    # Step 2: Convert the pixel coordinates to camera coordinates
    cam_vec = Camera.get_3D_camera_coords(int(u), int(v), Z_c, intrinsics["intrinsics_raw"])

    # print (f"Point in camera coordinates: ({cam_vec[0]}, {cam_vec[1]}, {cam_vec[2]})")

    # Step 3: Transform the camera coordinates to AprilTag coordinates
    rmat = np.array(april_tag_pose[0])
    tvec = np.array(april_tag_pose[1])

    # print(f"Rotation matrix: {rmat}")
    # print(f"Translation vector: {tvec}")

    # Inverse of the rotation matrix
    rinv = rmat.T

    # Calculate the AprilTag coordinates
    ATvec = np.dot(rinv, cam_vec - tvec)
    
    return ATvec

def open_image_in_paint(image_path: str) -> None:
    """
    Open an image in MS Paint and create two new layers.

    :param image_path: The path to the image
    """
    if os.name != 'nt':
        print("This function is only supported on Windows.")
        return
    
    # Check if the image exists
    if os.path.isfile(image_path):
        process = subprocess.Popen(['mspaint', image_path]) # Open the image in MS Paint

        time.sleep(2) # Wait for MS Paint to open

        # Create two new layers
        pyautogui.hotkey('ctrl', 'shift', 'n')
        time.sleep(2)
        pyautogui.hotkey('ctrl', 'shift', 'n')

        process.wait()  # Wait until the user closes MS Paint

        print("MS paint is closed.")
    else:
        print(f"The image at {image_path} was not found.")

def show_img(image_path: str) -> None:
    """
    Show an image using opencv

    :param image_path: The path to the image
    """
    cv2.imshow("Image", cv2.imread(image_path))
    cv2.waitKey(0)


