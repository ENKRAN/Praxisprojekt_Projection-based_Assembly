from app.core.flowchart_manager import FlowchartManager
import shutil
from pathlib import Path

def testManagerLogic():
    output_dir = Path("app/resources/flowchart_dynamic")
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    output_svg_path = Path(f"{output_dir}/current_flowchart.svg")

    diagrams_tool_path = shutil.which("diagrams")
    if not diagrams_tool_path:
        print("Error: The 'diagrams' tool was not found in the system PATH.")
        print("Please make sure that Node.js is installed and you have installed '@diagrams/cli' globally (npm install -g @diagrams/cli@latest).")
        print("You may also need to restart your terminal and VS Code or restart your system for the PATH to be recognized correctly.")
        return
    
    print("--- Testing Flowchart Manager ---")
    mgr = FlowchartManager()
    
    # 1. Start -> Operation
    mgr.addOperation("Step 1: Prep")
    
    # 2. Condition
    print(f"Adding Condition. Current Branch: {mgr.getActiveBranchName()}")
    mgr.addCondition("Is Parts Present?")
    
    # 3. NO Path (Auto-detected)
    print(f"Adding No Step. Current Branch: {mgr.getActiveBranchName()}")
    mgr.addOperation("Take Part")
    
    # 4. End of No Path (Trigger Backtrack)
    print("Ending No Branch...")
    mgr.addEnd()
    
    # 5. YES Path (Auto-detected after backtrack)
    print(f"Back on Branch: {mgr.getActiveBranchName()}")
    mgr.addOperation("Error: Search Part")
    
    # 6. End Logic
    mgr.addEnd()
    
    # Generate Flowchart SVG
    mgr.generateFlowchartSVG(diagrams_tool_path, output_svg_path)
    
    print("\nSUCCESS: Manager logic executed without errors.")

if __name__ == "__main__":
    testManagerLogic()