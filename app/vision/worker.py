import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from app.hardware.camera import CameraService
from app.vision.detector import AprilTagDetector
from app.vision.pose_estimator import PoseEstimator
from app.vision.visualization import drawAxes, drawTagBorderAndId
from app.core.config import Config

class VisionWorker(QThread):
    # Signals
    # Changed: pose_update_signal now includes the tag_id (int)
    pose_update_signal = pyqtSignal(np.ndarray, np.ndarray, int)  # R, t, tag_id
    
    # Changed: baking_update_signal now includes the tag_id
    baking_update_signal = pyqtSignal(np.ndarray, np.ndarray, int) # Homography, Image, tag_id
    
    image_update_signal = pyqtSignal(QImage)
    status_signal = pyqtSignal(str) 
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.snapshot_requested = False
        
        # Load Config
        calib = Config.getCalibration()
        self.cam_k = calib.cam_k
        self.cam_kc = calib.cam_kc
        
        # Init Logic
        self.width = 1280
        self.height = 720
        self.detector = AprilTagDetector(camera_intrinsics=self.cam_k)
        self.estimator = PoseEstimator(width=self.width, height=self.height)
        
    def triggerSnapshot(self):
        """Thread-safe trigger for snapshot."""
        print("VisionWorker: Snapshot requested.")
        self.snapshot_requested = True

    def run(self):
        self.is_running = True
        consecutive_failures = 0
        MAX_RETRIES = 5
        
        while self.is_running:
            try:
                self.status_signal.emit("Status: Connecting to Camera...")
                
                with CameraService(width=self.width, height=self.height, fps=30) as cam:
                    consecutive_failures = 0
                    self.status_signal.emit("Status: Live Feed Running")
                    
                    while self.is_running:
                        try:
                            success, color_img, depth_img = cam.getFrames()
                            if not success:
                                self.msleep(5)
                                continue

                            # 1. Detect Tags
                            gray = cv2.cvtColor(color_img, cv2.COLOR_BGR2GRAY)
                            tags = self.detector.detect(gray)

                            # --- DOMINANT TAG LOGIC ---
                            if tags:
                                # Filter: Select the tag with the largest area (closest to camera)
                                # This ensures we only process ONE tag at a time, avoiding ambiguity.
                                best_tag = max(tags, key=lambda t: abs(t.homography[0][0] * t.homography[1][1]))
                                
                                # Process only the best tag
                                R_ct, t_final = self.estimator.processTag(best_tag, depth_img, cam.depth_scale)
                                
                                # Snapshot Logic
                                if self.snapshot_requested:
                                    print(f"VisionWorker: Snapshot taken for Tag {best_tag.tag_id}")
                                    # Pass Tag ID to the baking signal!
                                    self.baking_update_signal.emit(best_tag.homography, color_img, best_tag.tag_id)
                                    self.snapshot_requested = False
                                
                                # Pose Update (Always emit for live projection)
                                self.pose_update_signal.emit(R_ct, t_final, best_tag.tag_id)
                                
                                # Visualization (Draw only the active tag)
                                color_img = drawTagBorderAndId(color_img, best_tag)
                                color_img = drawAxes(color_img, R_ct, t_final, self.cam_k, self.cam_kc, axis_length=0.05)
                            
                            # If no tags found, we simply don't emit pose updates, 
                            # so the projection stays where it was or hides (depending on implementation).

                            qt_img = self._convertCvToQt(color_img)
                            self.image_update_signal.emit(qt_img)

                        except RuntimeError as e:
                            print(f"VisionWorker: Camera stream interrupted: {e}")
                            break 
                            
            except Exception as e:
                print(f"VisionWorker: Connection Error: {e}")
                consecutive_failures += 1
                if consecutive_failures >= MAX_RETRIES:
                    self.status_signal.emit("Status: Connection Failed.")
                    self.error_signal.emit(str(e))
                    self.is_running = False
                    break
                if self.is_running:
                    self.status_signal.emit(f"Status: Connection Lost. Retrying ({consecutive_failures}/{MAX_RETRIES})...")
                    self.msleep(2000)
                else:
                    break

    def stop(self):
        self.is_running = False
        self.wait()

    def _convertCvToQt(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        return QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()