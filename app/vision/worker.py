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
    pose_update_signal = pyqtSignal(np.ndarray, np.ndarray)    # R, t
    baking_update_signal = pyqtSignal(np.ndarray, np.ndarray)  # Homography, Image
    image_update_signal = pyqtSignal(QImage)                   # GUI Image
    status_signal = pyqtSignal(str)                            # Status for the GUI (e.g. "Connecting...", "Live Feed Running", "Error", etc.)
    error_signal = pyqtSignal(str)                             # Critical error signal (only emitted when max retries reached)

    def __init__(self):
        super().__init__()
        self.is_running = True
        self.snapshot_requested = False
        
        # Load Config (Calibration)
        calib = Config.getCalibration()
        self.cam_k = calib.cam_k
        self.cam_kc = calib.cam_kc
        
        # Initialize Logic Components
        # Note: We use 1280x720 as standard resolution
        self.width = 1280
        self.height = 720
        
        self.detector = AprilTagDetector(camera_intrinsics=self.cam_k)
        self.estimator = PoseEstimator(width=self.width, height=self.height)
        
    def triggerSnapshot(self):
        """Thread-safe trigger for snapshot."""
        print("VisionWorker: Snapshot requested.")
        self.snapshot_requested = True

    def run(self):
        """
        Main loop with limited automatic reconnection mechanism.
        """
        self.is_running = True
        consecutive_failures = 0
        MAX_RETRIES = 5  # Gib nach 5 Versuchen (ca. 10 Sekunden) auf
        
        # Outer Loop: Connection Lifecycle
        while self.is_running:
            try:
                self.status_signal.emit("Status: Connecting to Camera...")
                
                # Context Manager handles Start/Stop automatically
                with CameraService(width=self.width, height=self.height, fps=30) as cam:
                    
                    # Wenn wir hier sind, hat die Verbindung geklappt -> Reset Counter
                    consecutive_failures = 0
                    self.status_signal.emit("Status: Live Feed Running")
                    
                    # Inner Loop: Frame Processing
                    while self.is_running:
                        try:
                            # 1. Fetch Data
                            success, color_img, depth_img = cam.getFrames()
                            if not success:
                                self.msleep(5)
                                continue

                            # 2. Detection & Logic
                            gray = cv2.cvtColor(color_img, cv2.COLOR_BGR2GRAY)
                            tags = self.detector.detect(gray)

                            for tag in tags:
                                R_ct, t_final = self.estimator.processTag(tag, depth_img, cam.depth_scale)
                                
                                if self.snapshot_requested:
                                    print("VisionWorker: Snapshot taken.")
                                    self.baking_update_signal.emit(tag.homography, color_img)
                                    self.snapshot_requested = False
                                
                                self.pose_update_signal.emit(R_ct, t_final)
                                
                                color_img = drawTagBorderAndId(color_img, tag)
                                color_img = drawAxes(color_img, R_ct, t_final, self.cam_k, self.cam_kc, axis_length=0.05)

                            qt_img = self._convertCvToQt(color_img)
                            self.image_update_signal.emit(qt_img)

                        except RuntimeError as e:
                            # Frame retrieval failed (Cable pulled?)
                            print(f"VisionWorker: Camera stream interrupted: {e}")
                            break # Break inner loop -> Trigger retry logic
                            
            except Exception as e:
                # Initialization failed or Crash occurred
                print(f"VisionWorker: Connection Error: {e}")
                
                consecutive_failures += 1
                
                if consecutive_failures >= MAX_RETRIES:
                    error_msg = f"Connection failed after {MAX_RETRIES} attempts.\nLast Error: {e}"
                    self.status_signal.emit("Status: Connection Failed.")
                    self.error_signal.emit(error_msg) # Trigger Popup in GUI
                    self.is_running = False # Stop the worker completely
                    break
                
                if self.is_running:
                    self.status_signal.emit(f"Status: Connection Lost. Retrying ({consecutive_failures}/{MAX_RETRIES})...")
                    self.msleep(2000) # Wait 2s before retry
                else:
                    break

    def stop(self):
        self.is_running = False
        self.wait()

    def _convertCvToQt(self, cv_img):
        """Convert OpenCV BGR to QImage."""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        return QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()