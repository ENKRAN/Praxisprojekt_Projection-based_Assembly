from pyflowchart import StartNode, EndNode, OperationNode, ConditionNode, InputOutputNode, SubroutineNode, Flowchart
from typing import List
import tempfile
import subprocess
from pathlib import Path
import shutil
import re

class FlowchartManager:    
    def __init__(self):
        self.diagrams_tool_path = shutil.which("diagrams")
        if not self.diagrams_tool_path:
            print("Error: The 'diagrams' tool was not found in the system PATH.")
            print("Please make sure that Node.js is installed and you have installed '@diagrams/cli' globally (npm install -g @diagrams/cli@latest).")
            print("You may also need to restart your terminal and VS Code or restart your system for the PATH to be recognized correctly.")
            return
        
        # 1. Initialize State
        self.start_node = StartNode("")  # Implicit "Start" text
        self.start_node.node_name = "node_0"
        self.current_node = self.start_node
        self.flowchart_done = False

        self._node_uid_map = {self.start_node: "node_0"}  # Map to track unique IDs for nodes (for flowchart logic saving)

        self.graph_data = {
            "nodes": [{"id": "node_0", "type": "start", "text": "", "step_folder": None}],
            "edges": []
        }
        
        # 2. Internal Branching Logic
        self._current_branch = "main"
        self._branch_counter = 1
        
        # Mapping: Branch Name -> Status ("Active", "Completed")
        self._branches_status = {self._current_branch: "Active"} 
        
        # Stack to track branch order for backtracking
        self._branches_stack = [self._current_branch] 
        
        # Mapping: Branch Name -> List of ConditionNodes within this branch
        self._condition_nodes_map = {self._current_branch: []}
        
        # "Yes" or "No" state for the current condition
        self._current_branch_state_yn = None 
        self._is_merging = False

        output_dir = Path("app/resources/flowchart_dynamic")
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

        self.output_svg_path = Path(f"{output_dir}/current_flowchart.svg")

    def addOperation(self, text: str, uid: str) -> OperationNode:
        node = OperationNode(text)
        node.node_name = uid
        self._node_uid_map[node] = uid
        return self._connectNode(node)

    def addCondition(self, text: str, uid: str) -> ConditionNode:
        node = ConditionNode(text)
        node.node_name = uid
        self._node_uid_map[node] = uid
        return self._connectNode(node)

    def addInputOutput(self, io_type: str, text: str, uid: str) -> InputOutputNode:
        if io_type == "input":
            node = InputOutputNode(InputOutputNode.INPUT, text)
        elif io_type == "output":
            node = InputOutputNode(InputOutputNode.OUTPUT, text)
        else:
            raise ValueError("Invalid io_type.")
        node.node_name = uid # <--- NEU
        self._node_uid_map[node] = uid
        return self._connectNode(node)
        
    def addSubroutine(self, text: str, uid: str) -> SubroutineNode:
        node = SubroutineNode(text)
        node.node_name = uid
        self._node_uid_map[node] = uid
        return self._connectNode(node)

    def addEnd(self, uid: str) -> EndNode:
        node = EndNode("")
        node.node_name = uid
        self._node_uid_map[node] = uid
        return self._connectNode(node)

    def getCurrentNodeName(self) -> str:
        return self.current_node.node_name

    def getActiveBranchName(self) -> str:
        return self._current_branch

    def getDSL(self) -> str:
        """
        Returns the flowchart DSL string for SVG generation.
        
        Returns:
            str: The flowchart DSL representation.
        """
        fc = Flowchart(self.start_node)
        return fc.flowchart()
    
    def addNode(self, node_type: str, text: str = "", io_text: str = "", node_uid: str = "", step_folder: str = ""):
        """
        Unified method to add a node based on type and string input.
        """
        # 1. Determine display text based on node type and input
        display_text = text
        if node_type == "inputoutput":
            display_text = f"{text.capitalize()}: {io_text}"
            
        # 2. Add node to internal graph data for logic saving
        self.graph_data["nodes"].append({
            "id": node_uid,
            "type": node_type,
            "text": display_text,
            "step_folder": step_folder
        })

        # 3. Do the actual node creation and connection in the flowchart structure
        match node_type:
            case "operation":
                return self.addOperation(text, node_uid)
            case "condition":
                return self.addCondition(text, node_uid)
            case "inputoutput":
                # text = 'input' or 'output', io_text = the actual text in the node
                return self.addInputOutput(text, io_text, node_uid)
            case "subroutine":
                return self.addSubroutine(text, node_uid)
            case "end":
                return self.addEnd(node_uid)

    def getMergeCandidates(self) -> List[ConditionNode]:
        """
        Returns a list of ConditionNodes that are valid targets for a merge.

        Returns:
            List[ConditionNode]: List of candidate ConditionNodes for merging.
        """
        # Logic: Only allow merge if not in Yes-Branch and not in Main
        if self._current_branch_state_yn == "Yes" or self._current_branch == "main":
            return []
            
        candidates = []
        # Find all "Yes" branches or main
        for branch in self._branches_stack:
            if "(Yes)" in branch or branch == "main":
                # Get all conditions in this branch
                candidates.extend(self._condition_nodes_map.get(branch, []))
        return candidates

    def mergeWithCondition(self, condition_node_text: str) -> bool:
        """
        Merges the current path back to a specific existing condition node.

        Args:
            condition_node_text (str): The text of the target ConditionNode to merge with.

        Returns:
            bool: True if merge was successful, False otherwise.
        """
        target_node = None
        # Search for the node by text
        for node_list in self._condition_nodes_map.values():
            for node in node_list:
                if node.node_text == condition_node_text:
                    target_node = node
                    break
        
        if target_node:
            print("Merging with node:", target_node)
            self._is_merging = True
            # Temporarily treat logic as if adding a node, but connecting to existing one
            previous_node = self.current_node
            self._connectPreviousToExistingCondition(previous_node, target_node)
            return True
        return False
    
    def checkMergePossibility(self) -> bool:
        """
        Checks if merging is currently possible based on the flowchart state.

        Returns:
            bool: True if merging is possible, False otherwise.
        """
        return self._current_branch_state_yn == "No" and not isinstance(self.current_node, ConditionNode)
    
    def _connectNode(self, new_node):
        """
        Connects self.current_node to new_node based on the current state and branching logic.

        Args:
            new_node: The new node to connect to.
        """
        previous_node = self.current_node

        edge_label = "next"
        if isinstance(previous_node, ConditionNode):
            edge_label = self._current_branch_state_yn

        # 1. Guard: Cannot connect FROM an EndNode (Legacy parity + Safety)
        if isinstance(previous_node, EndNode):
            print("Error: Cannot add a node after an EndNode. Please check branch logic.")
            return False

        # 2. Logic for standard nodes (Op, IO, Sub)
        if isinstance(new_node, (OperationNode, InputOutputNode, SubroutineNode)):
            if not isinstance(previous_node, ConditionNode):
                previous_node.connect(new_node)
            else:
                self._connectToCondition(previous_node, new_node)
            
            # Update pointer
            self.current_node = new_node

        # 3. Logic for Conditions (Branching)
        elif isinstance(new_node, ConditionNode):
            
            # LOGIC FIX: Check if previous is NOT a ConditionNode first (Legacy Parity)
            if not isinstance(previous_node, ConditionNode):
                
                # A. Init Main Branch State
                if self._current_branch == "main" and self._current_branch_state_yn is None:
                    self._current_branch_state_yn = "Yes"

                # B. Visual Layout Direction (To keep connections consequent)
                if self._current_branch_state_yn == "No":
                    previous_node.connect(new_node, "right")
                else:
                    previous_node.connect(new_node, "bottom")
            
            else:
                # Previous WAS a ConditionNode -> Connect to Yes/No port
                self._connectToCondition(previous_node, new_node)

            # Register logic for the new branch (Legacy: addConditionBranch)
            self._registerNewBranch(new_node)
            self.current_node = new_node

        # 4. Logic for End Nodes
        elif isinstance(new_node, EndNode):
            if isinstance(previous_node, StartNode):
                print("Error: Cannot connect StartNode directly to EndNode. Please add intermediate nodes.")
                return False
            
            if isinstance(previous_node, ConditionNode):
                self._connectToCondition(previous_node, new_node)
            else:
                previous_node.connect(new_node)

            if self._current_branch == "main":
                self.flowchart_done = True
                self.current_node = new_node # Pointer stays on EndNode
            else:
                self._switchToPreviousBranch()
                # Pointer is updated inside _switchToPreviousBranch

        self.graph_data["edges"].append({
            "from": self._node_uid_map.get(previous_node, "unknown"),
            "to": self._node_uid_map.get(new_node, "unknown"),
            "label": edge_label
        })

        return True
        
    def _connectToCondition(self, condition_node, new_node):
        """
        Helper to connect based on Yes/No state.
        
        Args:
            condition_node: The ConditionNode to connect from.
            new_node: The new node to connect to.
        """
        if self._current_branch_state_yn == "Yes":
            condition_node.connect_yes(new_node)
        else:
            condition_node.connect_no(new_node)
        
        if self._is_merging:
            self._is_merging = False

    def _registerNewBranch(self, condition_node):
        """
        Registers a new branch when a ConditionNode is added.

        Args:
            condition_node: The newly added ConditionNode.
        """
        # 1. Add current condition to the map of the CURRENT branch
        self._condition_nodes_map[self._current_branch].append(condition_node)
        self._branch_counter += 1
        
        # 2. Toggle Yes/No (Legacy: happens BEFORE creating name/pushing stack)
        self._toggleBranchStateYN()
        
        # 3. Generate new branch name
        new_branch_name = f"branch_{self._branch_counter - 1}_{condition_node.node_name} ({self._current_branch_state_yn})"
        
        # 4. Activate new branch
        self._branches_status[new_branch_name] = "Active"
        self._branches_stack.append(new_branch_name)
        
        # 5. Switch context
        self._current_branch = new_branch_name
        
        # Init map for the new branch
        self._condition_nodes_map.setdefault(new_branch_name, []).append(condition_node)

    def _switchToPreviousBranch(self):
        """
        Backtracking logic to find the next active open branch.
        """
        # 1. Mark current branch as completed
        self._branches_status[self._current_branch] = "Completed"
        
        found_active = False
        current_idx = self._branches_stack.index(self._current_branch)
        
        # 2. Iterate backwards to find an active branch
        for branch in self._branches_stack[current_idx - 1::-1]:
            if self._branches_status[branch] != "Completed":
                
                # 3. Resume from the last condition node of that branch
                last_cond = self._condition_nodes_map[branch][-1]
                self.current_node = last_cond
                self._current_branch = branch
                found_active = True
                break
        
        # 4. Toggle State YN implies we are now exploring the 'No' path of that condition
        if found_active:
            self._toggleBranchStateYN()
            print(f"Backtracked to: {self._current_branch}, State: {self._current_branch_state_yn}")

    def _toggleBranchStateYN(self):
        if self._current_branch_state_yn == "Yes":
            self._current_branch_state_yn = "No"
        else:
            self._current_branch_state_yn = "Yes"

    def _connectPreviousToExistingCondition(self, previous_node, target_condition_node):
        """
        Special case for Merge: Connect previous -> existing condition.
        Replicates the 'is_merging' block from legacy 'connectPreviousToNewNode'.

        Args:
            previous_node: The node to connect from.
            target_condition_node: The existing ConditionNode to connect to.
        """
        edge_label = "next"
        if isinstance(previous_node, ConditionNode):
            edge_label = self._current_branch_state_yn

        # Enforced "right" connection for merges
        previous_node.connect(target_condition_node, "right")

        self.graph_data["edges"].append({
            "from": self._node_uid_map.get(previous_node, "unknown"),
            "to": self._node_uid_map.get(target_condition_node, "unknown"),
            "label": edge_label
        })
        
        # After connecting, we need to backtrack because this path is closed
        self._switchToPreviousBranch()

        self._is_merging = False

    def generateFlowchartSVG(self):
        """
        Generates an SVG file from the current flowchart DSL using the specified diagrams tool.
        """
        if self.current_node == self.start_node:
            print("Flowchart is empty (only StartNode). Skipping SVG generation to prevent CLI freeze.")
            # Create a dummy SVG to prevent broken image in the GUI and indicate that the flowchart is empty
            with open(self.output_svg_path, 'w', encoding='utf-8') as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>')
            return

        flowchart_dsl = self.getDSL()
        print("Flowchart DSL generated: \n----------------------------------------------------------------------")
        print(flowchart_dsl)
        print("----------------------------------------------------------------------")

        temp_dsl_file = None    
        try:
            # 2. Write DSL to a temporary file with LF line endings (LF is important for compatibility with the diagrams tool because Windows uses CRLF by default!!!)
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".flowchart", encoding="utf-8", newline='\n') as temp_dsl_file:
                temp_dsl_file.write(flowchart_dsl)
                temp_dsl_path = Path(temp_dsl_file.name) # Use Path object
            print(f"Step 2: Flowchart DSL saved to temporary file: {temp_dsl_path} \n")

            # 3. Call `seflless/diagrams` CLI tool
            print(f"Step 3: Converting DSL to SVG with '{self.diagrams_tool_path} flowchart' CLI tool... \n")
            command = [
                self.diagrams_tool_path, # Dynamically found path
                "flowchart",
                str(temp_dsl_path), # Convert Path to string for the command
                str(self.output_svg_path)    # Convert Path to string for the command
            ]
            
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=10)

            print(f"Command executed: {' '.join(command)}")

            print(f"Step 4: SVG file successfully created at: {self.output_svg_path} \n")

            print("Step 5: Adjusting SVG colors for dark mode...")
            try:
                # 1. Read the generated SVG file
                with open(self.output_svg_path, 'r', encoding='utf-8') as svg_file:
                    svg_content = svg_file.read()

                # 2. Fix for the specific marker block (Diamond nodes) which has hardcoded black fill in the marker definition
                svg_content = svg_content.replace(
                    'id="raphael-marker-block"', 
                    'id="raphael-marker-block" fill="#d8dee9"'
                )

                # 3. Robust regex-based color replacement for the main elements:
                
                # Edges and node borders (Black -> Nord Light Grey)
                svg_content = re.sub(
                    r'stroke=["\'](?:#000000|#000|black)["\']', 
                    'stroke="#d8dee9"', 
                    svg_content, 
                    flags=re.IGNORECASE
                )
                
                # Text (Black -> Nord White) 
                svg_content = re.sub(
                    r'fill=["\'](?:#000000|#000|black)["\']', 
                    'fill="#eceff4"', 
                    svg_content, 
                    flags=re.IGNORECASE
                )

                # Node background (White -> Nord Dark Grey)
                svg_content = re.sub(
                    r'fill=["\'](?:#ffffff|#fff|white)["\']', 
                    'fill="#4c566a"', 
                    svg_content, 
                    flags=re.IGNORECASE
                )

                # 4. Overwrite the file with the new dark mode content
                with open(self.output_svg_path, 'w', encoding='utf-8') as svg_file:
                    svg_file.write(svg_content)
                    
                print("Step 5: Colors successfully adjusted! \n")
                
            except Exception as e:
                print(f"Error while recoloring the SVG: {e}")
        except subprocess.TimeoutExpired:
            print("CRITICAL ERROR: The 'diagrams' CLI tool took too long and was killed! Your GUI was saved from freezing.")
            # Dummy SVG to prevent broken image in the GUI and indicate an error occurred
            with open(self.output_svg_path, 'w', encoding='utf-8') as f:
                f.write('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><text x="0" y="10" fill="red">Flowchart Render Error</text></svg>')
        except subprocess.CalledProcessError as e:
            print(f"Error executing the '{self.diagrams_tool_path}' tool:")
            print(f"Return code: {e.returncode}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            print("Possible reason: The provided DSL is faulty or the tool could not read/write the files.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            # Use Path object for file operations
            if temp_dsl_path.exists():
                temp_dsl_path.unlink()
                print(f"Temporary DSL file deleted: {temp_dsl_path}")

    def updateFlowchart(self):
        self.generateFlowchartSVG()