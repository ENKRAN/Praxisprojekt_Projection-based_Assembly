import numpy as np
import time
from typing import Tuple, Any
from OneEuroFilter import OneEuroFilter

class PoseEstimator:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        
        # Filter Configuration (Legacy values)
        self.filter_config = {
            'freq': 60,       
            'mincutoff': 1.0, 
            'beta': 0.01,       
            'dcutoff': 1.0    
        }
        self.filter = None # Lazy initialization

    def processTag(self, tag: Any, depth_img: np.ndarray, depth_scale: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculates the stabilized 3D position of a tag using Depth Fusion and OneEuroFilter.

        Args:
            tag: Detected tag object with pose_R, pose_t, and center attributes.
            depth_img: Depth image as a 2D numpy array.
            depth_scale: Scale factor to convert raw depth to meters.

        Returns:
            R_ct: Rotation matrix of the tag.
            t_final: Stabilized translation vector of the tag.
        """
        # 1. Extract Raw Pose from RGB detection
        R_ct = tag.pose_R
        t_rgb = tag.pose_t.flatten()
        
        # 2. Depth Fusion Logic
        tag_cx, tag_cy = int(tag.center[0]), int(tag.center[1])
        
        # ROI Extraction
        v_min, v_max = max(0, tag_cy-2), min(self.height, tag_cy+3)
        u_min, u_max = max(0, tag_cx-2), min(self.width, tag_cx+3)
        
        depth_roi = depth_img[v_min:v_max, u_min:u_max]
        valid_pixels = depth_roi[depth_roi > 0]

        t_final = t_rgb # Fallback

        if len(valid_pixels) > 0:
            z_raw = np.median(valid_pixels)
            z_measured = z_raw * depth_scale
            
            # 3. OneEuro Filtering
            curr_time = time.time()
            if self.filter is None:
                self.filter = OneEuroFilter(**self.filter_config)
                z_filtered = z_measured
            else:
                z_filtered = self.filter(z_measured, curr_time)

            # 4. Fusion
            if t_rgb[2] != 0:
                scale = z_filtered / t_rgb[2]
                t_final = t_rgb * scale
                print(f"[Depth Fusion] t_rgb Z: {t_rgb[2]:.4f}m, Sensor Z: {z_filtered:.4f}m, Scale applied: {scale:.4f}")

            return R_ct, t_final