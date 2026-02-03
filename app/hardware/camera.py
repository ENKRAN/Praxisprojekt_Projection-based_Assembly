import pyrealsense2 as rs
import numpy as np
import time
from typing import Tuple, Optional

class CameraService:
    def __init__(self, width=1280, height=720, fps=30):
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        
        self.width = width
        self.height = height
        self.fps = fps
        
        # Configure streams
        self.config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
        self.config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
        
        self.align = None
        self.profile = None
        self.started = False
        self.depth_scale = 1.0

    def start(self):
        if self.started:
            return

        try:
            self.profile = self.pipeline.start(self.config)
            
            depth_sensor = self.profile.get_device().first_depth_sensor()
            self.depth_scale = depth_sensor.get_depth_scale()
            
            self.align = rs.align(rs.stream.color)
            
            self.started = True
            print(f"CameraService started. Depth Scale: {self.depth_scale}")
            
            for _ in range(10):
                self.pipeline.wait_for_frames()
                
        except Exception as e:
            self.started = False
            # WICHTIG: Den Fehler werfen, damit der Worker ihn bemerkt!
            raise RuntimeError(f"Could not start camera: {e}")

    def stop(self):
        if self.started:
            self.pipeline.stop()
            self.started = False
            print("CameraService stopped.")

    def getFrames(self) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Fetches synchronized color and depth frames.
        Raises RuntimeError if retrieval fails (e.g. device disconnected).
        """
        if not self.started:
             # If we are not started, this is a logic error in the caller
            raise RuntimeError("CameraService: getFrames called but camera not started.")

        try:
            # We assume: If this times out or fails, the device is likely gone/stuck.
            frames = self.pipeline.wait_for_frames(timeout_ms=2000)
            
            aligned_frames = self.align.process(frames)
            color_frame = aligned_frames.get_color_frame()
            depth_frame = aligned_frames.get_depth_frame()
            
            if not color_frame or not depth_frame:
                # Frame incomplete, but connection might be okay. 
                # We return False to skip this frame, but don't crash.
                return False, None, None
            
            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(depth_frame.get_data())
            
            return True, color_image, depth_image

        except Exception as e:
            # Critical error (Timeout, Disconnect, USB Error)
            # Re-raise to trigger recovery in Worker
            raise RuntimeError(f"Frame retrieval failed: {e}")

    # --- Utils for Projection (RealSense specific) ---

    @staticmethod
    def get3DPoint(u, v, depth_val, intrinsics):
        """
        Wrapper for deprojection using RealSense intrinsics.

        Args:
            u (int): Pixel x-coordinate.
            v (int): Pixel y-coordinate.
            depth_val (float): Depth value at the pixel.
            intrinsics: RealSense intrinsics object.

        Returns:
            np.ndarray: 3D point as [x, y, z].
        """
        point = rs.rs2_deproject_pixel_to_point(intrinsics, [u, v], depth_val)
        return np.array(point)

    @staticmethod
    def get2DPixel(point_3d, intrinsics):
        """
        Wrapper for projection using RealSense intrinsics.

        Args:
            point_3d (np.ndarray or list): 3D point as [x, y, z].
            intrinsics: RealSense intrinsics object.

        Returns:
            tuple: (u, v) pixel coordinates.
        """
        if isinstance(point_3d, np.ndarray):
            point_3d = point_3d.flatten().tolist()
        pixel = rs.rs2_project_point_to_pixel(intrinsics, point_3d)
        return int(pixel[0]), int(pixel[1])
    
    @staticmethod
    def numpyToRsIntrinsics(K, dist_coeffs, width, height):
        """
        Converts numpy camera matrix to RealSense intrinsics object.

        Args:
            K (np.ndarray): Camera intrinsic matrix.
            dist_coeffs (np.ndarray or list): Distortion coefficients.
            width (int): Image width.
            height (int): Image height.
        
        Returns:
            rs.intrinsics: RealSense intrinsics object.
        """
        intrin = rs.intrinsics()
        intrin.width = int(width)
        intrin.height = int(height)
        intrin.ppx = float(K[0, 2])
        intrin.ppy = float(K[1, 2])
        intrin.fx = float(K[0, 0])
        intrin.fy = float(K[1, 1])
        
        if dist_coeffs is not None:
            coeffs_list = dist_coeffs.flatten().tolist() if isinstance(dist_coeffs, np.ndarray) else list(dist_coeffs)
            # Ensure correct length (5 coeffs for Brown-Conrady)
            coeffs_list = (coeffs_list + [0.0]*5)[:5]
            intrin.model = rs.distortion.brown_conrady
            intrin.coeffs = coeffs_list
        else:
            intrin.model = rs.distortion.none
            intrin.coeffs = [0.0]*5

        return intrin

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()