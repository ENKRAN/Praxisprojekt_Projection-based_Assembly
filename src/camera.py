import pyrealsense2 as rs
import numpy as np
from typing import Tuple

class Camera:
    """
    Class to interface with a RealSense camera
    """
    def __init__(self, width=640, height=480, fps=60, enable_depth=True, enable_color=True) -> None:
        self.pipeline = rs.pipeline()
        self.config = rs.config()

        # Enable color stream if desired
        if enable_color:
            self.config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)

        # Enable depth stream if desired
        if enable_depth:
            self.config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)

        self.profile = self.pipeline.start(self.config)

        # Optional: Get depth scale
        if enable_depth:
            depth_sensor = self.profile.get_device().first_depth_sensor()
            self.depth_scale = depth_sensor.get_depth_scale()
        else:
            self.depth_scale = None

    def get_frames(self) -> Tuple[rs.frame, rs.frame, np.ndarray, np.ndarray]:
        """
        Get color and depth frames from the camera, along with their numpy array representations.

        :return: Tuple of color_frame, depth_frame (pyrealsense2 frames) and color_image, depth_image (numpy arrays)
        """
        frames = self.pipeline.wait_for_frames()
        align_to = rs.stream.color
        align = rs.align(align_to)
        aligned_frames = align.process(frames)

        # Get color frame (if enabled)
        color_frame = aligned_frames.get_color_frame()

        # Get depth frame (if enabled)
        depth_frame = aligned_frames.get_depth_frame()

        if not color_frame or not depth_frame:
            print("Fehler beim Abrufen der Frames.")
            return None, None, None, None

        # Convert frames to numpy arrays
        color_image = np.asanyarray(color_frame.get_data())
        depth_image = np.asanyarray(depth_frame.get_data())

        return color_frame, depth_frame, color_image, depth_image


    def get_color_sensor_intrinsics(self) -> Tuple[float, float, float, float, np.ndarray]:
        """
        Get the intrinsics of the color sensor

        :return: Tuple of fx, fy, ppx, ppy, and the distortion coefficients
        """
        # Hole das aktive Farbprofil
        color_stream = self.profile.get_stream(rs.stream.color)
        video_stream_profile = color_stream.as_video_stream_profile()
        intrinsics = video_stream_profile.get_intrinsics()

        return intrinsics.fx, intrinsics.fy, intrinsics.ppx, intrinsics.ppy, np.array(intrinsics.coeffs)


    def stop(self) -> None:
        """
        Stop the camera pipeline
        """
        self.pipeline.stop()
