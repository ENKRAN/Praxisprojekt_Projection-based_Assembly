import pyrealsense2 as rs
import numpy as np
from typing import Tuple, Dict, Optional
import cv2

class Camera:
    """
    Class to interface with a RealSense camera
    """
    def __init__(self, color_width=1920, color_height=1080, depth_width=1280, depth_height=720, fps=30, enable_depth=True, enable_color=True) -> None:
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
            self.config.enable_stream(rs.stream.color, color_width, color_height, rs.format.bgr8, fps)

        # Enable depth stream if desired
        if enable_depth:
            self.config.enable_stream(rs.stream.depth, depth_width, depth_height, rs.format.z16, fps)

        self.profile = self.pipeline.start(self.config)

        # Optional: Get depth scale
        if enable_depth:
            depth_sensor = self.profile.get_device().first_depth_sensor()
            self.depth_scale = depth_sensor.get_depth_scale()
        else:
            self.depth_scale = None

    def get_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[rs.frame], Optional[rs.frame], Optional[float]]:        
        """
        Get color and depth frames from the camera, along with their numpy array representations.

        :return: Tuple of color_frame, depth_frame (pyrealsense2 frames) and color_image, depth_image (numpy arrays)
        """
        success = False
        frames = self.pipeline.wait_for_frames()
        align_to = rs.stream.color
        align = rs.align(align_to)
        aligned_frames = align.process(frames)

        # Get color frame (if enabled)
        color_frame = aligned_frames.get_color_frame()

        # Get depth frame (if enabled)
        depth_frame = aligned_frames.get_depth_frame()

        if not color_frame or not depth_frame:
            print("Error: No frames received")
            return None, None, None, None
        
        success = True

        # Convert frames to numpy arrays
        color_image = np.asanyarray(color_frame.get_data())
        depth_image = np.asanyarray(depth_frame.get_data())

        return success, color_image, color_frame, depth_image, depth_frame, self.depth_scale

    def get_color_sensor_intrinsics(self) -> Dict:
        """
        Get the intrinsics of the color sensor as a dictionary.

        :return: Tuple of fx, fy, ppx, ppy, the distortion coefficients and the raw intrinsics
        """
        color_stream = self.profile.get_stream(rs.stream.color)
        video_stream_profile = color_stream.as_video_stream_profile()
        intrinsics = video_stream_profile.get_intrinsics()

        return {
            "width": intrinsics.width,
            "height": intrinsics.height,
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

    @staticmethod
    def get_3D_camera_coords_realsense(u, v, z, intrinsics) -> np.ndarray:
        """
        Get the 3D coordinates of a pixel in the camera frame with the RealSense library.

        :param u: x pixel coordinate
        :param v: y pixel coordinate
        :param z: Depth value
        :param intrinsics: Intrinsics of the camera
        :return: 3D coordinates as a numpy array
        """
        x, y, z = rs.rs2_deproject_pixel_to_point(intrinsics, [u, v], z)

        t_depth_vec =  np.array([x, y, z]).reshape(3, 1)

        return t_depth_vec
    
    @staticmethod
    def get_3D_camera_coords_opencv(u, v, cam_K, cam_kc, depth_frame) -> np.ndarray:
        """
        Get the 3D coordinates of a pixel in the camera frame with OpenCV.

        :param u: x pixel coordinate
        :param v: y pixel coordinate
        :param cam_K: Camera matrix
        :param cam_kc: Distortion coefficients
        :param depth_frame: Depth frame
        :return: 3D coordinates as a numpy array
        """
        # Convert pixel coordinates to a numpy array for undistortion
        point = np.array([[[u, v]]], dtype=np.float32)
        
        # Undistort the pixel coordinates
        undistorted_points = cv2.undistortPoints(point, cam_K, cam_kc)
        x_c = undistorted_points[0, 0, 0]
        y_c = undistorted_points[0, 0, 1]
        
        # Get the depth value from the depth frame
        Z_c = depth_frame.get_distance(int(u), int(v))
        
        if Z_c <= 0 or np.isnan(Z_c):
            raise ValueError(f"Invalid depth value at ({u}, {v}): {Z_c}")
        
        # Calculate the 3D coordinates
        X_c = x_c * Z_c
        Y_c = y_c * Z_c
        
        # Create a numpy array with the 3D coordinates
        point_3D = np.array([[X_c], [Y_c], [Z_c]])
        
        return point_3D
    
    @staticmethod
    def get_2D_camera_coords(intrinsics, tvec) -> Tuple[int, int]:
        """
        Get the pixel coordinates of a 3D point in the camera frame.

        :param depth_intrinsics: Intrinsics of the depth sensor
        :param tvec: Translation vector
        :return: Tuple of x, y pixel coordinates
        """
        x, y, z = tvec
        u, v = rs.rs2_project_point_to_pixel(intrinsics, [x, y, z])

        return int(u), int(v)

    def stop(self) -> None:
        """
        Stop the camera pipeline
        """
        self.pipeline.stop()
