from pyflowchart import StartNode, EndNode, OperationNode, ConditionNode, InputOutputNode, SubroutineNode, Flowchart
from typing import List, Optional, Dict, Any

class FlowchartManager:
    def __init__(self):
        # 1. Initialize State
        self.start_node = StartNode("")  # Implicit "Start" text
        self.current_node = self.start_node
        self.flowchart_done = False
        
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

    # --- Public API (Used by GUI) ---

    def addOperation(self, text: str) -> OperationNode:
        node = OperationNode(text)
        self._connectNode(node)
        return node

    def addCondition(self, text: str) -> ConditionNode:
        node = ConditionNode(text)
        self._connectNode(node)
        return node

    def addInputOutput(self, io_type: str, text: str) -> InputOutputNode:
        """ io_type should be 'input' or 'output' """
        node = InputOutputNode(io_type, text) 
        self._connectNode(node)
        return node
        
    def addSubroutine(self, text: str) -> SubroutineNode:
        node = SubroutineNode(text)
        self._connectNode(node)
        return node

    def addEnd(self) -> EndNode:
        node = EndNode("End")
        self._connectNode(node)
        return node

    def getCurrentNodeName(self) -> str:
        return self.current_node.node_name

    def getActiveBranchName(self) -> str:
        return self._current_branch

    def getDSL(self) -> str:
        """Returns the flowchart DSL string for SVG generation."""
        fc = Flowchart(self.start_node)
        return fc.flowchart()

    def getMergeCandidates(self) -> List[ConditionNode]:
        """Returns a list of ConditionNodes that are valid targets for a merge."""
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
        """Merges the current path back to a specific existing condition node."""
        target_node = None
        # Search for the node by text
        for node_list in self._condition_nodes_map.values():
            for node in node_list:
                if node.node_text == condition_node_text:
                    target_node = node
                    break
        
        if target_node:
            self._is_merging = True
            # Temporarily treat logic as if adding a node, but connecting to existing one
            previous_node = self.current_node
            self._connectPreviousToExistingCondition(previous_node, target_node)
            return True
        return False

    # --- Internal Logic (The "Brain") ---
    
    def _connectNode(self, new_node):
        """
        Connects self.current_node to new_node based on the current state engine.
        Replicates the exact logic from legacy 'connectPreviousToNewNode'.
        """
        previous_node = self.current_node
        
        # 1. Guard: Is flowchart already done?
        if self.flowchart_done:
            print("Warning: Flowchart is already done.")
            return

        # 2. Guard: Cannot connect FROM an EndNode (Legacy parity + Safety)
        if isinstance(previous_node, EndNode):
            print("Error: Cannot add a node after an EndNode. Please check branch logic.")
            return

        # 3. Logic for standard nodes (Op, IO, Sub)
        if isinstance(new_node, (OperationNode, InputOutputNode, SubroutineNode)):
            if not isinstance(previous_node, ConditionNode):
                previous_node.connect(new_node)
            else:
                self._connectToCondition(previous_node, new_node)
            
            # Update pointer
            self.current_node = new_node

        # 4. Logic for Conditions (Branching)
        elif isinstance(new_node, ConditionNode):
            
            # LOGIC FIX: Check if previous is NOT a ConditionNode first (Legacy Parity)
            if not isinstance(previous_node, ConditionNode):
                
                # A. Init Main Branch State
                if self._current_branch == "main" and self._current_branch_state_yn is None:
                    self._current_branch_state_yn = "Yes"

                # B. Handle Merge Mode
                if self._is_merging:
                    # Legacy: Force connection to "right"
                    previous_node.connect(new_node, "right")
                    self._switchToPreviousBranch()
                    self._is_merging = False
                    # Pointer is NOT updated to new_node, as we jumped back!
                    return 

                # C. Visual Layout Direction (To keep connections consequent)
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

        # 5. Logic for End Nodes
        elif isinstance(new_node, EndNode):
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

    def _connectToCondition(self, condition_node, new_node):
        """Helper to connect based on Yes/No state."""
        if self._current_branch_state_yn == "Yes":
            condition_node.connect_yes(new_node)
        else:
            condition_node.connect_no(new_node)
        
        if self._is_merging:
            self._is_merging = False

    def _registerNewBranch(self, condition_node):
        """
        Prepares the state for a new branch.
        Replicates legacy 'addConditionBranch'.
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
        if new_branch_name not in self._condition_nodes_map:
            self._condition_nodes_map[new_branch_name] = []

    def _switchToPreviousBranch(self):
        """
        Backtracking logic to find the next active open branch.
        Replicates legacy 'switchToPreviousBranch'.
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
        """
        # Legacy: enforced "right" connection for merges
        previous_node.connect(target_condition_node, "right")
        
        # After connecting, we need to backtrack because this path is closed
        self._switchToPreviousBranch()