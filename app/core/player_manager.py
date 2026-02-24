import json
from pathlib import Path

class PlayerManager:
    def __init__(self):
        self.manual_dir = None
        self.manual_config = None
        self.flowchart_data = None
        
        # Runtime state
        self.current_node_id = None
        self.current_step_folder = None
        self.is_finished = False

        self.history_stack = []

    def loadManual(self, manual_id: str) -> bool:
        """
        Loads the manual configuration and flowchart for the given manual_id.
        """
        self.manual_dir = Path(f"data/manuals/{manual_id}")
        config_path = self.manual_dir / "manual_config.json"
        flowchart_path = self.manual_dir / "flowchart.json"

        if not config_path.exists() or not flowchart_path.exists():
            print(f"Error: Missing files for manual {manual_id}")
            return False

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.manual_config = json.load(f)
            
            with open(flowchart_path, 'r', encoding='utf-8') as f:
                flowchart_json = json.load(f)
                self.flowchart_data = flowchart_json.get("graph", {})
                
            # Start with the initial node and reset state
            self.history_stack = []
            self.current_node_id = "node_0"
            self.is_finished = False
            self.advance("next") 
            
            return True
        except Exception as e:
            print(f"Error loading manual for playback: {e}")
            return False

    def advance(self, choice: str = "next") -> bool:
        """
        Advances to the next node based on the user's choice.

        Args:
            choice (str): The label of the edge to follow. Default is "next".
        """
        if not self.flowchart_data or self.is_finished:
            return False

        # Find the right edge based on the current node and the user's choice
        edges = self.flowchart_data.get("edges", [])
        next_node_id = None
        
        for edge in edges:
            if edge["from"] == self.current_node_id and edge["label"].lower() == choice.lower():
                next_node_id = edge["to"]
                break
                
        if not next_node_id:
            print(f"Warning: No valid path found from {self.current_node_id} with choice '{choice}'")
            return False
        
        self.history_stack.append(self.current_node_id)

        # Update the current node
        self.current_node_id = next_node_id
        
        # Get the new node data and update the step folder and finished state
        node_data = self.getNodeData(self.current_node_id)
        if node_data:
            self.current_step_folder = node_data.get("step_folder")
            if node_data.get("type") == "end":
                self.is_finished = True
                self.current_step_folder = None
                
        return True

    def getNodeData(self, node_id: str) -> dict:
        """
        Retrieves the data for a given node ID from the flowchart.
        """
        if not self.flowchart_data:
            return {}
        nodes = self.flowchart_data.get("nodes", [])
        for node in nodes:
            if node["id"] == node_id:
                return node
        return {}

    def getCurrentNodeInfo(self) -> dict:
        """
        Returns the current node information, including type, text, step folder, and tracking data.
        """
        data = self.getNodeData(self.current_node_id)
        
        # We search for tracking data (homography) in the manual configuration for the current node
        tracking_data = {}
        if self.manual_config:
            steps = self.manual_config.get("steps", [])
            for step in steps:
                if step.get("node_uid") == self.current_node_id:
                    tracking_data["tag_id"] = step.get("tag_id")
                    tracking_data["homography_matrix"] = step.get("homography_matrix")
                    break

        return {
            "node_id": self.current_node_id,
            "type": data.get("type", "unknown"),
            "text": data.get("text", ""),
            "step_folder": self.current_step_folder,
            "is_finished": self.is_finished,
            "tracking_data": tracking_data
        }

    def getPaths(self):
        """
        Returns the paths to the snapshot and SVG for the current step, if available.
        """
        if not self.current_step_folder or not self.manual_dir:
            return None, None
            
        step_dir = self.manual_dir / "steps" / self.current_step_folder
        snapshot_path = step_dir / "snapshot.png"
        svg_path = step_dir / "drawing.svg"
        
        return str(snapshot_path), str(svg_path)
    
    def goBack(self) -> bool:
        """
        Goes back to the previous node in the history stack, if possible.
        """
        if not self.history_stack:
            return False
            
        # Pop the last node ID from the history stack to go back
        prev_node_id = self.history_stack.pop()
        
        # Update the current node to the previous one
        self.current_node_id = prev_node_id
        self.is_finished = False 
        
        # Update the current step folder based on the new node
        node_data = self.getNodeData(self.current_node_id)
        if node_data:
            self.current_step_folder = node_data.get("step_folder")
            
        return True