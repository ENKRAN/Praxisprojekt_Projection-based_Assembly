from pyflowchart import StartNode, EndNode, OperationNode, ConditionNode, InputOutputNode, SubroutineNode, Flowchart
from typing import List

class FlowchartManager:
    def __init__(self):
        # 1. Initialize State
        self.startNode = StartNode("Start")
        self.currentNode = self.startNode
        self.flowchartDone = False
        
        # 2. Internal Branching Logic
        self._currentBranch = "main"
        self._branchCounter = 1
        
        # Mapping: Branch Name -> Status ("Active", "Completed")
        self._branchesStatus = {self._currentBranch: "Active"} 
        
        # Stack to track branch order for backtracking
        self._branchesStack = [self._currentBranch] 
        
        # Mapping: Branch Name -> List of ConditionNodes within this branch
        self._conditionNodesMap = {self._currentBranch: []}
        
        # "Yes" or "No" state for the current condition
        self._currentBranchStateYN = None 
        self._isMerging = False

    # --- Public API (Used by GUI) ---

    def addOperation(self, text: str) -> OperationNode:
        node = OperationNode(text)
        self._connectNode(node)
        return node

    def addCondition(self, text: str) -> ConditionNode:
        node = ConditionNode(text)
        self._connectNode(node)
        return node

    def addInputOutput(self, ioType: str, text: str) -> InputOutputNode:
        """ ioType should be 'input' or 'output' """
        node = InputOutputNode(ioType, text) 
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
        return self.currentNode.node_name

    def getActiveBranchName(self) -> str:
        return self._currentBranch

    def getDSL(self) -> str:
        """Returns the flowchart DSL string for SVG generation."""
        fc = Flowchart(self.startNode)
        return fc.flowchart()

    def getMergeCandidates(self) -> List[ConditionNode]:
        """Returns a list of ConditionNodes that are valid targets for a merge."""
        # Logic: Only allow merge if not in Yes-Branch and not in Main
        if self._currentBranchStateYN == "Yes" or self._currentBranch == "main":
            return []
            
        candidates = []
        # Find all "Yes" branches or main
        for branch in self._branchesStack:
            if "(Yes)" in branch or branch == "main":
                # Get all conditions in this branch
                candidates.extend(self._conditionNodesMap.get(branch, []))
        return candidates

    def mergeWithCondition(self, conditionNodeText: str) -> bool:
        """Merges the current path back to a specific existing condition node."""
        targetNode = None
        # Search for the node by text
        for nodeList in self._conditionNodesMap.values():
            for node in nodeList:
                if node.node_text == conditionNodeText:
                    targetNode = node
                    break
        
        if targetNode:
            self._isMerging = True
            # Temporarily treat logic as if adding a node, but connecting to existing one
            previousNode = self.currentNode
            self._connectPreviousToExistingCondition(previousNode, targetNode)
            return True
        return False

    # --- Internal Logic (The "Brain") ---
    
    def _connectNode(self, newNode):
        """
        Connects self.currentNode to newNode based on the current state engine.
        """
        previousNode = self.currentNode
        
        # 1. Guard: Is flowchart already done?
        if self.flowchartDone:
            print("Warning: Flowchart is already done.")
            return

        # 2. Logic for standard nodes (Op, IO, Sub)
        if isinstance(newNode, (OperationNode, InputOutputNode, SubroutineNode)):
            if isinstance(previousNode, ConditionNode):
                self._connectToCondition(previousNode, newNode)
            else:
                previousNode.connect(newNode)
            
            # Update pointer
            self.currentNode = newNode

        # 3. Logic for Conditions (Branching)
        elif isinstance(newNode, ConditionNode):
            # Handle Merge Mode
            if self._isMerging:
                previousNode.connect(newNode, "right")
                self._switchToPreviousBranch()
                self._isMerging = False
                # Pointer is NOT updated to newNode, as we jumped back!
                return 

            # Standard Connection
            if isinstance(previousNode, ConditionNode):
                # Special Case: Condition immediately after Condition
                if self._currentBranch == "main" and self._currentBranchStateYN is None:
                    self._currentBranchStateYN = "Yes"
                
                # Direction decision based on Yes/No
                if self._currentBranchStateYN == "No":
                    previousNode.connect(newNode, "right")
                else:
                    previousNode.connect(newNode, "bottom")
            else:
                previousNode.connect(newNode)

            # Register logic for the new branch
            self._registerNewBranch(newNode)
            self.currentNode = newNode

        # 4. Logic for End Nodes
        elif isinstance(newNode, EndNode):
            if isinstance(previousNode, ConditionNode):
                self._connectToCondition(previousNode, newNode)
            else:
                previousNode.connect(newNode)

            if self._currentBranch == "main":
                self.flowchartDone = True
                self.currentNode = newNode
            else:
                self._switchToPreviousBranch()
                # Pointer is updated inside _switchToPreviousBranch

    def _connectToCondition(self, conditionNode, newNode):
        """Helper to connect based on Yes/No state."""
        if self._currentBranchStateYN == "Yes":
            conditionNode.connect_yes(newNode)
        else:
            conditionNode.connect_no(newNode)
        
        if self._isMerging:
            self._isMerging = False

    def _registerNewBranch(self, conditionNode):
        """Prepares the state for a new branch."""
        # Add current condition to the map
        self._conditionNodesMap[self._currentBranch].append(conditionNode)
        self._branchCounter += 1
        
        # Toggle Yes/No for the NEXT step
        self._toggleBranchStateYN()
        
        # Generate new branch name
        newBranchName = f"branch_{self._branchCounter - 1}_{conditionNode.node_name} ({self._currentBranchStateYN})"
        
        self._branchesStatus[newBranchName] = "Active"
        self._branchesStack.append(newBranchName)
        self._currentBranch = newBranchName
        
        # Init map for the new branch
        if newBranchName not in self._conditionNodesMap:
            self._conditionNodesMap[newBranchName] = []

    def _switchToPreviousBranch(self):
        """Backtracking logic to find the next active open branch."""
        # Mark current as completed
        self._branchesStatus[self._currentBranch] = "Completed"
        
        foundActive = False
        currentIdx = self._branchesStack.index(self._currentBranch)
        
        # Iterate backwards from current branch
        for branch in self._branchesStack[currentIdx - 1::-1]:
            if self._branchesStatus[branch] != "Completed":
                # Jump back to this branch
                # Get the last condition node of this branch to resume from
                lastCond = self._conditionNodesMap[branch][-1]
                self.currentNode = lastCond
                self._currentBranch = branch
                foundActive = True
                break
        
        if foundActive:
            self._toggleBranchStateYN()
            print(f"Backtracked to: {self._currentBranch}, State: {self._currentBranchStateYN}")

    def _toggleBranchStateYN(self):
        if self._currentBranchStateYN == "Yes":
            self._currentBranchStateYN = "No"
        else:
            self._currentBranchStateYN = "Yes"

    def _connectPreviousToExistingCondition(self, previousNode, targetConditionNode):
        """Special case for Merge: Connect previous -> existing condition."""
        self._isMerging = True
        
        # Default connect behavior (delegates to standard logic but with merge flag)
        previousNode.connect(targetConditionNode) 
        
        # After connecting, we need to backtrack because this path is closed
        self._switchToPreviousBranch()
        self._isMerging = False