import pyrealsense2 as rs
import numpy as np
import time

class Camera():
    def __init__(self, width=1280, height=720, fps=30):
        """
        Initializes the RealSense pipeline.
        For simplicity, we use the same resolution for color and depth,
        since we align them anyway.
        """
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        
        # Configuration
        self.width = width
        self.height = height
        self.fps = fps
        
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
            # Start pipeline
            self.profile = self.pipeline.start(self.config)
            
            depth_sensor = self.profile.get_device().first_depth_sensor()
            self.depth_scale = depth_sensor.get_depth_scale()
            
            # Create align object to align depth to color
            self.align = rs.align(rs.stream.color)
            
            self.started = True
            print(f"Camera started. Depth Scale: {self.depth_scale}")
            
            # Warmup: first frames are often dark or empty (auto-exposure needs time)
            for _ in range(10):
                self.pipeline.wait_for_frames()
                
        except Exception as e:
            print(f"Error starting camera: {e}")
            self.started = False

    def stop(self):
        if self.started:
            self.pipeline.stop()
            self.started = False
            print("Camera stopped.")

    def getFrames(self):
        """
        Gets aligned frames.
        Returns:
            success (bool), color_image (numpy), depth_image (numpy), intrinsics (obj)
        """
        if not self.started:
            print("Camera attempting restart...")
            self.start()
            time.sleep(1)

        try:
            frames = self.pipeline.wait_for_frames(timeout_ms=5000)
            
            aligned_frames = self.align.process(frames)
            
            color_frame = aligned_frames.get_color_frame()
            depth_frame = aligned_frames.get_depth_frame()
            
            if not color_frame or not depth_frame:
                return False, None, None
            
            # Convert to numpy for easier handling with OpenCV, etc.
            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(depth_frame.get_data())
            
            return True, color_image, depth_image

        except Exception as e:
            print(f"Frame retrieval error: {e}")
            return False, None, None

    @staticmethod
    def get3DPoint(u, v, depth_val, intrinsics):
        """
        Wrapper for deprojection.
        u, v: pixel coordinates
        depth_val: depth in meters (already multiplied by scale!)
        """
        # rs2_deproject_pixel_to_point returns [x, y, z] list
        point = rs.rs2_deproject_pixel_to_point(intrinsics, [u, v], depth_val)
        return np.array(point) # Return as flat array [x, y, z]

    @staticmethod
    def get2DPixel(point_3d, intrinsics):
        """
        Wrapper for projection.
        point_3d: [x, y, z] array or list
        """
        # Ensure it is a flat list/array
        if isinstance(point_3d, np.ndarray):
            point_3d = point_3d.flatten().tolist()
            
        pixel = rs.rs2_project_point_to_pixel(intrinsics, point_3d)
        return int(pixel[0]), int(pixel[1])
    
    @staticmethod
    def numpyToRsintrinsics(K, dist_coeffs, width, height):
        intrin = rs.intrinsics()
        
        intrin.width = int(width)
        intrin.height = int(height)
        
        intrin.ppx = float(K[0, 2])
        intrin.ppy = float(K[1, 2])
        intrin.fx = float(K[0, 0])
        intrin.fy = float(K[1, 1])
        
        if dist_coeffs is not None:
            if isinstance(dist_coeffs, np.ndarray):
                coeffs_list = dist_coeffs.flatten().tolist()
            else:
                coeffs_list = list(dist_coeffs)
            
            coeffs_list = [float(c) for c in coeffs_list]

            if len(coeffs_list) < 5:
                coeffs_list += [0.0] * (5 - len(coeffs_list))
            elif len(coeffs_list) > 5:
                coeffs_list = coeffs_list[:5]

            intrin.model = rs.distortion.brown_conrady
            intrin.coeffs = coeffs_list
        else:
            intrin.model = rs.distortion.none
            intrin.coeffs = [0.0, 0.0, 0.0, 0.0, 0.0]

        return intrin

    # Context manager support (with Camera() as cam:)   
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()