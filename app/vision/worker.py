import json
import time
from pathlib import Path

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from app.hardware.shared_camera_client import SharedCameraClient
from app.vision.detector import AprilTagDetector
from app.vision.pose_estimator import PoseEstimator
from app.vision.visualization import drawAxes, drawTagBorderAndId
from app.core.config import Config

# #region agent log
def _agent_debug_log(location: str, message: str, data: dict, hypothesis_id: str) -> None:
    try:
        log_path = Path(__file__).resolve().parents[2] / "debug-a32f16.log"
        payload = {
            "sessionId": "a32f16",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass


def _apply_homography_pixel(H: np.ndarray, x: float, y: float) -> tuple[float, float]:
    v = H @ np.array([x, y, 1.0], dtype=np.float64)
    w = float(v[2])
    if abs(w) < 1e-12:
        return float("nan"), float("nan")
    return float(v[0] / w), float(v[1] / w)
# #endregion

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

        self.is_debug = False
        self.debug_image_path = ""
        
        # Load Config
        calib = Config.getCalibration()
        self.cam_k = calib.cam_k
        self.cam_kc = calib.cam_kc
        
        # Init Logic
        self.width = 1280
        self.height = 720
        self.detector = AprilTagDetector(camera_intrinsics=self.cam_k)
        self.estimator = PoseEstimator(width=self.width, height=self.height)

    def setDebugMode(self, is_debug: bool, image_path: str = ""):
        """
        Enables or disables debug mode. In debug mode, the worker will load a static image from the specified path instead of connecting to the camera.
        This is useful for testing and development without needing the actual hardware.

        Args:
            is_debug (bool): Whether to enable debug mode.
            image_path (str): Path to the debug image to load when in debug mode. Ignored if is_debug is False.
        """
        self.is_debug = is_debug
        self.debug_image_path = image_path
        
    def triggerSnapshot(self):
        """Thread-safe trigger for snapshot."""
        print("VisionWorker: Snapshot requested.")
        self.snapshot_requested = True

    def run(self):
        self.is_running = True
        consecutive_failures = 0
        MAX_RETRIES = 5

        # --- DEBUG MODE (IF NO HARDWARE IS AVAILABLE) ---
        if self.is_debug:
            self.status_signal.emit("Status: DEBUG MODE - Loading static image")
            
            # Load the static image once
            static_img = cv2.imread(self.debug_image_path)
            if static_img is None:
                self.error_signal.emit(f"Debug Image not found at: {self.debug_image_path}")
                return

            # Dummy Depth Image (Not used for actual detection in debug, but required for method signature)
            depth_img = np.zeros((self.height, self.width), dtype=np.uint16)
            depth_scale = 0.001

            depth_img.fill(500)  # Simulate a flat surface at 0.5m distance

            while self.is_running:
                # We fake the camera feed by repeatedly processing the same static image. This allows us to test the detection and pose estimation logic without needing a live camera feed.
                color_img = static_img.copy() 
                
                self._process_frame(color_img, depth_img, depth_scale)
                
                # Short sleep to prevent maxing out CPU in this debug loop, since we're not waiting on actual camera frames. In a real scenario, the camera's frame rate would naturally limit this.
                self.msleep(33) 
                
            return
        
        # --- LIVE MODE (LABOTORY LIVE WITH HARDWARE) ---
        while self.is_running:
            try:
                self.status_signal.emit("Status: Connecting to Camera...")
                
                with SharedCameraClient() as cam:
                    consecutive_failures = 0
                    self.status_signal.emit("Status: Live Feed Running")
                    
                    while self.is_running:
                        try:
                            success, color_img, depth_img = cam.getFrames()
                            if not success:
                                self.msleep(5)
                                continue

                            self._process_frame(color_img, depth_img, cam.depth_scale)

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

    def _process_frame(self, color_img, depth_img, depth_scale):
        # 1. Detect Tags
        gray = cv2.cvtColor(color_img, cv2.COLOR_BGR2GRAY)
        tags = self.detector.detect(gray)

        # --- DOMINANT TAG LOGIC ---
        if tags:
            # Filter: Select the tag with the largest area (closest to camera)
            # This ensures we only process ONE tag at a time, avoiding ambiguity.
            best_tag = max(tags, key=lambda t: abs(t.homography[0][0] * t.homography[1][1]))
            
            # Process only the best tag
            R_ct, t_final = self.estimator.processTag(best_tag, depth_img, depth_scale)
            
            # Snapshot Logic
            if self.snapshot_requested:
                print(f"VisionWorker: Snapshot taken for Tag {best_tag.tag_id}")
                # #region agent log
                H = np.asarray(best_tag.homography, dtype=np.float64)
                ideal_ccw = [(-1.0, 1.0), (1.0, 1.0), (1.0, -1.0), (-1.0, -1.0)]
                pred = np.array(
                    [_apply_homography_pixel(H, x, y) for x, y in ideal_ccw],
                    dtype=np.float64,
                )
                meas = np.asarray(best_tag.corners, dtype=np.float64)
                pred_edges = sorted(
                    float(np.linalg.norm(pred[i] - pred[(i + 1) % 4])) for i in range(4)
                )
                meas_edges = sorted(
                    float(np.linalg.norm(meas[i] - meas[(i + 1) % 4])) for i in range(4)
                )
                ratios = [p / m for p, m in zip(pred_edges, meas_edges) if m > 1e-6]
                _agent_debug_log(
                    "worker.py:snapshot",
                    "frame, detector tag_size, homography vs corner edges",
                    {
                        "color_shape_hw": [int(color_img.shape[0]), int(color_img.shape[1])],
                        "matches_worker_wh": bool(
                            color_img.shape[1] == self.width and color_img.shape[0] == self.height
                        ),
                        "detector_tag_size": float(self.detector.tag_size),
                        "tag_id": int(best_tag.tag_id),
                        "pred_edge_lengths_px": pred_edges,
                        "meas_edge_lengths_px": meas_edges,
                        "pred_meas_edge_ratio_sorted_mean": float(np.mean(ratios)) if ratios else None,
                    },
                    "H4",
                )
                _agent_debug_log(
                    "worker.py:snapshot",
                    "resolution check for SVG vs homography pixel space",
                    {
                        "frame_w": int(color_img.shape[1]),
                        "frame_h": int(color_img.shape[0]),
                        "expected_svg_space_w": int(self.width),
                        "expected_svg_space_h": int(self.height),
                    },
                    "H2",
                )
                # #endregion
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

    def stop(self):
        self.is_running = False
        self.wait()

    def _convertCvToQt(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        return QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()