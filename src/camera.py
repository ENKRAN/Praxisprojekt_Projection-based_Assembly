import pyrealsense2 as rs
import numpy as np
from typing import Tuple, Dict, List, Any

class Camera:
    """
    Class to interface with a RealSense camera
    """
    def __init__(self, width=640, height=480, fps=60, enable_depth=True, enable_color=True) -> None:
        """
        Initialize the camera pipeline with the desired settings.

        :param width: Width of the frames
        :param height: Height of the frames
        :param fps: Frames per second
        :param enable_depth: Enable depth stream
        :param enable_color: Enable color stream
        """
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

    def get_frames(self) -> Tuple[np.ndarray, np.ndarray, Any, Any]:
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

        return color_image, depth_image, depth_frame, color_frame

    def get_color_sensor_intrinsics(self) -> Dict:
        """
        Get the intrinsics of the color sensor as a dictionary.

        :return: Tuple of fx, fy, ppx, ppy, the distortion coefficients and the raw intrinsics
        """
        color_stream = self.profile.get_stream(rs.stream.color)
        video_stream_profile = color_stream.as_video_stream_profile()
        intrinsics = video_stream_profile.get_intrinsics()

        return {
            "fx": intrinsics.fx,
            "fy": intrinsics.fy,
            "ppx": intrinsics.ppx,
            "ppy": intrinsics.ppy,
            "dist_coeffs": np.array(intrinsics.coeffs),
            "intrinsics_raw": intrinsics
        }

    def get_depth_sensor_intrinsics(self) -> Dict:
        """
        Get the intrinsics of the depth sensor

        :return: Tuple of fx, fy, ppx, ppy, the distortion coefficients and the raw intrinsics
        """
        depth_stream = self.profile.get_stream(rs.stream.depth)
        video_stream_profile = depth_stream.as_video_stream_profile()
        intrinsics = video_stream_profile.get_intrinsics()

        return {
            "fx": intrinsics.fx,
            "fy": intrinsics.fy,
            "ppx": intrinsics.ppx,
            "ppy": intrinsics.ppy,
            "dist_coeffs": np.array(intrinsics.coeffs),
            "intrinsics_raw": intrinsics
        }

    def get_3d_coordinates(self, u, v, depth_to_tag, intrinsics) -> np.ndarray[Any, np.dtype]:
        """
        Get 3D coordinates of the center of the detected Apriltag.

        :param u: x-coordinate of the center of the tag
        :param v: y-coordinate of the center of the tag
        :param depth_to_tag: Depth to the tag (z-coordinate)
        :param intrinsics: Intrinsics of the depth sensor
        :return: 3D coordinates of the center of the tag
        """
        x, y, depth_to_tag = rs.rs2_deproject_pixel_to_point(intrinsics, [u, v], depth_to_tag)

        t_depth_vec =  np.array([x, y, depth_to_tag]).reshape(3, 1)

        return t_depth_vec

    def stop(self) -> None:
        """
        Stop the camera pipeline
        """
        self.pipeline.stop()
