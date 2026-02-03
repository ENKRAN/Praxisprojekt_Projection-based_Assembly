import json
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict

@dataclass
class StepData:
    """Represents a single step in the assembly manual."""
    step_id: int
    node_uid: str           # Links to Flowchart Node ID (e.g., UUID or name)
    node_type: str          # e.g., "operation", "decision"
    description: str
    
    # File Paths (Relative to manual folder)
    snapshot_file: str
    drawing_file: str
    
    # Spatial Data: Homography (Image Plane -> Tag Plane)
    # We store it as a list of lists for JSON compatibility
    homography_matrix: List[List[float]] 
    tag_id: int

    def get_homography(self) -> np.ndarray:
        """Returns the homography as a numpy array."""
        return np.array(self.homography_matrix, dtype=np.float32)

@dataclass
class ManualData:
    """Represents the complete manual."""
    id: str                 # Unique Folder Name
    title: str              # Human readable title
    created_at: str
    tag_id: int             # The reference tag ID for this manual
    
    steps: List[StepData] = field(default_factory=list)
    flowchart_dsl: str = "" 
    
    def to_json(self, path: str):
        """Saves the manual data to a JSON file."""
        data = asdict(self)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    @classmethod
    def from_json(cls, path: str):
        """Loads manual data from a JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Reconstruct StepData objects from dicts
        steps_raw = data.get("steps", [])
        steps_obj = [StepData(**s) for s in steps_raw]
        
        return cls(
            id=data["id"],
            title=data["title"],
            created_at=data["created_at"],
            tag_id=data.get("tag_id", 0),
            steps=steps_obj,
            flowchart_dsl=data.get("flowchart_dsl", "")
        )