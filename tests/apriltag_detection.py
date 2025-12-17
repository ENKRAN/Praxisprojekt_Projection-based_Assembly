import numpy as np
import cv2
import time
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QImage
from OneEuroFilter import OneEuroFilter

from src.camera import Camera
from src.apriltag_detection import AprilTagDetector
from src.visualization import drawAxes, drawTagBorderAndId

class AprilTagTrackingWorker(QThread):
    # Signals for the GUI (thread-safe communication)
    # sends: (image_qt, pose_text, depth_val)
    pose_update_signal = pyqtSignal(np.ndarray, np.ndarray)
    baking_update_signal = pyqtSignal(np.ndarray)
    image_update_signal = pyqtSignal(QImage) 
    
    def __init__(self, width=1280, height=720, cam_intrinsics=None, cam_dist_coeffs=None):
        super().__init__()
        self.width = width
        self.height = height
        self.is_running = True
        self.cam_intrinsics = cam_intrinsics
        self.cam_dist_coeffs = cam_dist_coeffs
        
        # Detector initialization (expensive, only do once)
        self.apriltag_detector = AprilTagDetector(camera_intrinsics=cam_intrinsics)
        
        # Filter (initialization happens on first measurement)
        self.filter = None 

        self.snapshot_requested = False

    def triggerSnapshot(self):
        """Is called from the GUI thread to request a snapshot."""
        print("Snapshot requested!")
        self.snapshot_requested = True

    def run(self):
        """
        This is where the separate thread runs.
        The GUI does not freeze because we loop here.
        """
        # Here we use your Camera class as a context manager!
        # This guarantees that the camera shuts down when the thread ends.
        with Camera(width=self.width, height=self.height, fps=30) as cam:
            
            while self.is_running:
                # 1. Get data
                success, color_img, depth_img = cam.getFrames()
                if not success:
                    self.msleep(10) # Wait briefly, reduce CPU usage
                    continue

                # 2. AprilTag detection
                gray = cv2.cvtColor(color_img, cv2.COLOR_BGR2GRAY)
                
                tags = self.apriltag_detector.detect(gray_frame=gray)

                # 3. Logic per tag (fusion & filter)
                for tag in tags:
                    # A. Ray scaling approach
                    R_ct = tag.pose_R
                    t_rgb = tag.pose_t.flatten()
                    tag_cx, tag_cy = int(tag.center[0]), int(tag.center[1])
                    
                    # Get ROI from depth map
                    v_min, v_max = max(0, tag_cy-2), min(self.height, tag_cy+3)
                    u_min, u_max = max(0, tag_cx-2), min(self.width, tag_cx+3)
                    depth_roi = depth_img[v_min:v_max, u_min:u_max]
                    valid_pixels = depth_roi[depth_roi > 0]

                    if len(valid_pixels) > 0:
                        z_raw = np.median(valid_pixels)
                        z_measured = z_raw * cam.depth_scale
                        
                        # B. 1€ filter
                        curr_time = time.time()
                        
                        if self.filter is None:
                            self.filter = OneEuroFilter(curr_time, z_measured, min_cutoff=1.0, beta=0.01)
                            z_filtered = z_measured
                        else:
                            z_filtered = self.filter(z_measured, curr_time)

                        # C. Fusion
                        if t_rgb[2] != 0:
                            scale = z_filtered / t_rgb[2]
                            t_final = t_rgb * scale

                            if self.snapshot_requested:
                                print("Sending snapshot homography...")
                                self.baking_update_signal.emit(tag.homography)
                                self.snapshot_requested = False
                            
                            self.pose_update_signal.emit(R_ct, t_final)
                            
                            # Draw for visualization
                            color_img = drawTagBorderAndId(color_img, tag)
                            color_img = drawAxes(color_img, R_ct, t_final, self.cam_intrinsics, 
                                                 self.cam_dist_coeffs, axis_length=0.05)

                # 4. Convert image for GUI
                qt_img = self._convertCvToQt(color_img)
                
                # 5. Send data to GUI
                self.image_update_signal.emit(qt_img)

    def stop(self):
        self.is_running = False
        self.wait() # Wait until the thread terminates cleanly

    def _convertCvToQt(self, cv_img):
        """Helper function: OpenCV BGR -> Qt Image"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w

        return QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()