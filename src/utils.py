import subprocess
import os
import time
import pyautogui
import cv2
import numpy as np

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

def show_depth_image(depth_image, debug_mode="colormap") -> None:
    """
    Display the depth image using OpenCV

    :param depth_image: The depth image
    :param debug_mode: The debug mode to use
    """
    if debug_mode == "colormap":
        depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.03), cv2.COLORMAP_JET)
        cv2.imshow('Depth Image', depth_colormap)
    elif debug_mode == "smoothed":
        smoothed_depth = cv2.GaussianBlur(depth_image, (5, 5), 0)
        depth_colormap_smoothed = cv2.applyColorMap(cv2.convertScaleAbs(smoothed_depth, alpha=0.03), cv2.COLORMAP_JET)
        cv2.imshow('Depth Image smoothed', depth_colormap_smoothed)
    elif debug_mode == "filtered":
        valid_depth = np.where(smoothed_depth > 0, smoothed_depth, 0)
        depth_colormap_valid = cv2.applyColorMap(cv2.convertScaleAbs(valid_depth, alpha=0.03), cv2.COLORMAP_JET)
        cv2.imshow('Depth Image valid', depth_colormap_valid)

    cv2.waitKey(0)

