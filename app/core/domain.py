from dataclasses import dataclass
from typing import List
import numpy as np

@dataclass
class PoseData:
    """Stores position data (e.g., from AprilTag)."""
    # Stored as list for easy JSON serialization.
    # Converted to numpy arrays when needed.
    matrix_data: List[float] 

    def toNumpy(self) -> np.ndarray:
        return np.array(self.matrix_data).reshape((4, 4))

@dataclass
class InstructionContent:
    """
    The actual content of a work step.
    Separates data (image, drawing) from logic (flowchart nodes).
    """
    step_id: str
    image_path: str               # Path to snapshot (original image)
    svg_path: str                 # Path to saved SVG drawing
    reference_tag_pose: PoseData  # The pose of the tag at the time of capture
    
    # Optional: Additional metadata
    created_at: float = 0.0
    description: str = ""