import json
import time
from pathlib import Path

from pupil_apriltags import Detector
import numpy as np
from typing import List, Any

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
# #endregion

class AprilTagDetector:
    def __init__(self, camera_intrinsics: np.ndarray, tag_family: str = "tagStandard41h12", tag_size: float = 0.038):
        self.detector = Detector(families=tag_family)
        
        self.fx = camera_intrinsics[0, 0]
        self.fy = camera_intrinsics[1, 1]
        self.cx = camera_intrinsics[0, 2]
        self.cy = camera_intrinsics[1, 2]
        self.tag_size = tag_size
        # #region agent log
        _agent_debug_log(
            "detector.py:__init__",
            "AprilTagDetector initialized",
            {
                "tag_size": float(tag_size),
                "fx": float(self.fx),
                "fy": float(self.fy),
                "cx": float(self.cx),
                "cy": float(self.cy),
            },
            "H1",
        )
        # #endregion

    def detect(self, gray_frame: np.ndarray) -> List[Any]:
        results = self.detector.detect(
            gray_frame, 
            estimate_tag_pose=True, 
            camera_params=[self.fx, self.fy, self.cx, self.cy], 
            tag_size=self.tag_size
        )
        return results