import cv2
import sys
import numpy as np
from screeninfo import get_monitors
from typing import Tuple, List
import pyrealsense2 as rs
from .image_processing import save_component_img
import os
import glob

def setup_projector_window():
    # Get the second screen (projector)
    monitors = get_monitors()
    if len(monitors) < 2:
        print("Error: No second screen found. Please connect a second screen and try again.")
        sys.exit()

    # Get the second screen properties
    second_screen = monitors[1]
    screen_x = second_screen.x
    screen_y = second_screen.y
    projector_width = 800
    projector_height = 600

    projector_window_name = 'Projector Window'

    cv2.namedWindow(projector_window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(projector_window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.moveWindow(projector_window_name, screen_x, screen_y)  # Positioning on second screen

    return projector_window_name, projector_width, projector_height
