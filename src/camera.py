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

    def get_frames(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get a color and depth frame from the camera

        :return: Tuple of color and depth frames
        """
        frames = self.pipeline.wait_for_frames()

        # Get color frame (if enabled)
        color_frame = frames.get_color_frame()

        # Get depth frame (if enabled)
        depth_frame = frames.get_depth_frame()

        # Convert frames to numpy arrays (if not None)
        color_image = np.asanyarray(color_frame.get_data()) if color_frame else None
        depth_image = np.asanyarray(depth_frame.get_data()) if depth_frame else None

        return color_image, depth_image

    def get_color_sensor_intrinsics(self) -> Tuple[float, float, float, float, np.ndarray]:
        """
        Get the intrinsics of the color sensor

        :return: Tuple of fx, fy, ppx, ppy, and the distortion coefficients
        """
        color_sensor = self.profile.get_device().first_color_sensor()
        intrinsics = color_sensor.get_stream_profiles()[0].as_video_stream_profile().get_intrinsics()

        return intrinsics.fx, intrinsics.fy, intrinsics.ppx, intrinsics.ppy, np.array(intrinsics.coeffs)

    def stop(self) -> None:
        """
        Stop the camera pipeline
        """
        self.pipeline.stop()
