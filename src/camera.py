import pyrealsense2 as rs
import numpy as np
from typing import Tuple, Dict, Optional
import cv2
import time

class Camera:
    def __init__(self, color_width=1280, color_height=720, depth_width=1280, depth_height=720, fps=30, enable_depth=True, enable_color=True) -> None:
        """
        Initialize the camera object with the desired settings.

        :param color_width: Width of the color stream
        :param color_height: Height of the color stream
        :param depth_width: Width of the depth stream
        :param depth_height: Height of the depth stream
        :param fps: Frames per second
        :param enable_depth: Enable depth stream
        :param enable_color: Enable color stream
        """
        # Initialize the pipeline and configuration
        self.pipeline = rs.pipeline()
        self.config = rs.config()

        # Flag to check if the camera is started
        self.started = False

        # Enable color stream if desired
        if enable_color:
            self.config.enable_stream(rs.stream.color, color_width, color_height, rs.format.bgr8, fps)

        # Enable depth stream if desired
        if enable_depth:
            self.config.enable_stream(rs.stream.depth, depth_width, depth_height, rs.format.z16, fps)

        # Start the camera
        self.start()

        # Optional: Get depth scale
        if enable_depth and self.started:
            depth_sensor = self.profile.get_device().first_depth_sensor()
            self.depth_scale = depth_sensor.get_depth_scale()
        else:
            self.depth_scale = None

    def start(self) -> None:
        """
        Start the camera with the desired configuration.
        """
        try:
            self.profile = self.pipeline.start(self.config)
            self.started = True
            print("Camera started successfully.")
        except Exception as e:
            print(f"Error starting camera: {e}")
            self.started = False

    def get_frames(self, max_retries=10) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[rs.frame], Optional[rs.frame], Optional[float]]:
        """
        Get the frames from the camera and retries if no frames are received.

        :param max_retries: Maximum number of retries to get frames
        :return: Tuple of color image, depth image, color frame, depth frame, depth scale
        """
        success = False
        retry_count = 0

        while retry_count < max_retries:
            try:
                if not self.started:
                    print("Camera not started. Starting camera...")
                    self.start()
                    time.wait(2)

                frames = self.pipeline.wait_for_frames(timeout_ms=5000)  # Timeout in 5 seconds

                # Align frames to the color stream
                align_to = rs.stream.color  # FIXME: Should not be in the main loop -> too expensive!
                align = rs.align(align_to)
                aligned_frames = align.process(frames)

                # Get color and depth frames
                color_frame = aligned_frames.get_color_frame()
                depth_frame = aligned_frames.get_depth_frame()

                if not color_frame or not depth_frame:
                    raise RuntimeError("No frames received")

                # Convert frames to numpy arrays for opencv
                color_image = np.asanyarray(color_frame.get_data())
                depth_image = np.asanyarray(depth_frame.get_data())

                success = True
                return success, color_image, color_frame, depth_image, depth_frame

            except Exception as e:
                print(f"Error: {e}")
                print(f"Retrying to get frames... Attempt {retry_count + 1} of {max_retries}")
                retry_count += 1

        # Return None if frames are not received after multiple attempts
        print("Failed to get frames after multiple attempts.")
        return False, None, None, None, None, None

    def get_color_sensor_intrinsics(self) -> Dict:
        """
        Get the intrinsics of the color sensor

        :return: Tuple of width, height, fx, fy, ppx, ppy, the distortion coefficients and the raw intrinsics
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
        Get the 3D coordinates of a pixel in the camera frame with functions from the RealSense library.

        :param u: x pixel coordinate
        :param v: y pixel coordinate
        :param z: Depth value
        :param intrinsics: Intrinsics of the color sensor
        :return: 3D coordinates as a 3x1 numpy array
        """
        x, y, z = rs.rs2_deproject_pixel_to_point(intrinsics, [u, v], z)

        point_3D =  np.array([x, y, z]).reshape(3, 1)

        return point_3D
    
    @staticmethod
    def get_3D_camera_coords_opencv(u, v, cam_K, cam_kc, depth_frame) -> np.ndarray:
        """
        Get the 3D coordinates of a pixel in the camera frame with OpenCV functions.

        :param u: x pixel coordinate
        :param v: y pixel coordinate
        :param cam_K: Camera matrix
        :param cam_kc: Distortion coefficients
        :param depth_frame: Depth frame
        :return: 3D coordinates as a 3x1 numpy array
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
    def get_2D_camera_coords(intrinsics, point_3D) -> Tuple[int, int]:
        """
        Project 3D coordinates to 2D pixel coordinates with functions from the RealSense library.

        :param intrinsics: Intrinsics of the color sensor
        :param point_3D: 3D coordinates as a 3x1 numpy array
        :return: Tuple of x and y pixel coordinates	
        """
        x, y, z = point_3D
        u, v = rs.rs2_project_point_to_pixel(intrinsics, [x, y, z])

        return int(u), int(v)

    def stop(self) -> None:
        """
        Stop the camera.
        """
        if self.started:
            try:
                self.pipeline.stop()
                self.started = False
                print("Camera stopped.")
            except Exception as e:
                print(f"Error stopping camera: {e}")
