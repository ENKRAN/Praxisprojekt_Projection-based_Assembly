import cv2
import numpy as np
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class CalibrationData:
    cam_k: np.ndarray
    cam_kc: np.ndarray
    proj_k: np.ndarray
    proj_kc: np.ndarray
    R: np.ndarray
    T: np.ndarray

class Config:
    _calibration_data: Optional[CalibrationData] = None

    @classmethod
    def loadCalibration(cls, file_path: str):
        """
        Loads camera and projector calibration from a YAML file.

        Args:
            file_path (str): Path to the calibration YAML file.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Calibration file not found: {file_path}")
            
        fs = cv2.FileStorage(file_path, cv2.FILE_STORAGE_READ)
        
        # Read matrices
        cam_k = fs.getNode('camK').mat()
        cam_kc = fs.getNode('camKc').mat()
        proj_k = fs.getNode('prjK').mat()
        proj_kc = fs.getNode('prjKc').mat()
        R = fs.getNode('R').mat()
        T = fs.getNode('T').mat()
        
        fs.release()
        
        # Basic validation
        if cam_k is None or proj_k is None:
            raise ValueError(f"Failed to load valid calibration data from {file_path}")
            
        cls._calibration_data = CalibrationData(cam_k, cam_kc, proj_k, proj_kc, R, T)
        print(f"Config: Calibration loaded successfully from {file_path}")

    @classmethod
    def getCalibration(cls) -> CalibrationData:
        if cls._calibration_data is None:
            raise RuntimeError("Calibration not loaded! Call Config.loadCalibration() first.")
        return cls._calibration_data