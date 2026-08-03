import os
import shutil
import datetime
from pathlib import Path
import numpy as np
import cv2
from typing import Optional
import json

from app.core.domain import ManualData, StepData

class ManualManager:
    BASE_DIR = Path("data/manuals")

    def __init__(self):
        self.current_manual: Optional[ManualData] = None
        self.current_manual_dir: Optional[Path] = None
        
        # Ensure base directory exists
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

    def createNewManual(self, title: str, tag_id: int) -> ManualData:
        """Creates a new manual structure on disk."""
        # Sanitize title for folder name (replace spaces with underscores)
        safe_title = "".join([c if c.isalnum() else "_" for c in title])
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        manual_id = f"{safe_title}_{timestamp}"
        
        self.current_manual_dir = self.BASE_DIR / manual_id
        
        # Create main folder
        try:
            self.current_manual_dir.mkdir(parents=True, exist_ok=True)
            (self.current_manual_dir / "steps").mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"Error creating manual directory: {e}")
            raise

        # Initialize Data Object
        self.current_manual = ManualData(
            id=manual_id,
            title=title,
            created_at=datetime.datetime.now().isoformat(),
            tag_id=tag_id,
            steps=[],
            flowchart_dsl=""
        )
        
        self.saveManifest()
        print(f"Manual '{title}' initialized at {self.current_manual_dir}")
        return self.current_manual

    def saveStep(self, 
                 step_id: int,
                 node_uid: str,
                 node_type: str, 
                 description: str,
                 snapshot_img: np.ndarray, 
                 svg_source_path: str,
                 homography: np.ndarray,
                 tag_id: int):
        """
        Saves a single step into its own subfolder.
        """
        if not self.current_manual or not self.current_manual_dir:
            raise RuntimeError("No active manual to save step to.")

        # 1. Create Step Subfolder (e.g. "steps/step_001")
        step_folder_name = f"step_{step_id:03d}"
        step_dir = self.current_manual_dir / "steps" / step_folder_name
        step_dir.mkdir(parents=True, exist_ok=True)

        # 2. Define File Paths
        snapshot_filename = "snapshot.png"
        drawing_filename = "drawing.svg"
        
        dest_snapshot = step_dir / snapshot_filename
        dest_drawing = step_dir / drawing_filename

        # 3. Save Assets
        # Save Image
        cv2.imwrite(str(dest_snapshot), snapshot_img)
        
        # Copy SVG
        if os.path.exists(svg_source_path):
            shutil.copy(svg_source_path, dest_drawing)
        else:
            print(f"Warning: SVG source not found at {svg_source_path}")

        # 4. Prepare Matrix for JSON
        homography_list = homography.tolist()

        # 5. Create Step Object (paths are relative to manual root)
        # Note: We use forward slashes for compatibility
        rel_snapshot_path = f"steps/{step_folder_name}/{snapshot_filename}"
        rel_drawing_path = f"steps/{step_folder_name}/{drawing_filename}"

        new_step = StepData(
            step_id=step_id,
            node_uid=node_uid,
            node_type=node_type,
            description=description,
            snapshot_file=rel_snapshot_path,
            drawing_file=rel_drawing_path,
            homography_matrix=homography_list,
            tag_id=tag_id
        )
        
        self.current_manual.steps.append(new_step)
        self.saveManifest()
        print(f"Step {step_id} saved successfully to {step_dir}.")

    def updateFlowchartDSL(self, dsl_text: str):
        """Updates the flowchart logic string."""
        if self.current_manual:
            self.current_manual.flowchart_dsl = dsl_text
            self.saveManifest()

    def saveManifest(self):
        """Writes manual_config.json."""
        if self.current_manual and self.current_manual_dir:
            json_path = self.current_manual_dir / "manual_config.json"
            self.current_manual.to_json(str(json_path))

    def saveFlowchartData(self, graph_data: dict, action_log: list):
        """Saves the logical flowchart structure AND the action log for resuming."""
        if self.current_manual_dir:
            json_path = self.current_manual_dir / "flowchart.json"
            data_to_save = {
                "graph": graph_data,
                "actions": action_log
            }
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)

    def listManuals(self, status_filter: str = None) -> list:
        """Returns list of (id, title) tuples, optionally filtered by status."""
        manuals = []
        for d in self.BASE_DIR.iterdir():
            if d.is_dir():
                config_path = d / "manual_config.json"
                if config_path.exists():
                    try:
                        with open(config_path, 'r') as f:
                            data = json.load(f)
                            # Fallback "draft", if status is missing (for backward compatibility)
                            manual_status = data.get("status", "draft") 
                            if status_filter is None or manual_status == status_filter:
                                manuals.append((data['id'], data['title']))
                    except Exception as e:
                        print(f"Error reading config {config_path}: {e}")
        return manuals

    def loadManualForEditing(self, manual_id: str) -> bool:
        """Sets up the manager to resume an existing draft."""
        manual_dir = self.BASE_DIR / manual_id
        config_path = manual_dir / "manual_config.json"
        
        if not config_path.exists():
            return False
            
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            
            # Reconstruct ManualData object
            steps_data = data.get("steps", [])
            steps_objects = [StepData(**s) for s in steps_data]
            
            self.current_manual = ManualData(
                id=data["id"],
                title=data["title"],
                created_at=data["created_at"],
                tag_id=data.get("tag_id", -1),
                steps=steps_objects,
                flowchart_dsl=data.get("flowchart_dsl", ""),
                status=data.get("status", "draft")
            )
            self.current_manual_dir = manual_dir
            return True
        except Exception as e:
            print(f"Error loading manual {manual_id}: {e}")
            return False

    def finalizeManual(self):
        """Marks the manual as published."""
        if self.current_manual:
            self.current_manual.status = "published"
            self.saveManifest()
            print(f"Manual {self.current_manual.id} finalized and published!")