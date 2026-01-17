from app.core.flowchart_manager import FlowchartManager

def testManagerLogic():
    print("--- Testing Flowchart Manager ---")
    mgr = FlowchartManager()
    
    # 1. Start -> Operation
    mgr.addOperation("Step 1: Prep")
    
    # 2. Condition
    print(f"Adding Condition. Current Branch: {mgr.getActiveBranchName()}")
    mgr.addCondition("Is Parts Present?")
    
    # 3. YES Path (Auto-detected)
    print(f"Adding Yes Step. Current Branch: {mgr.getActiveBranchName()}")
    mgr.addOperation("Take Part")
    
    # 4. End of Yes Path (Trigger Backtrack)
    print("Ending Yes Branch...")
    mgr.addEnd()
    
    # 5. NO Path (Auto-detected after backtrack)
    print(f"Back on Branch: {mgr.getActiveBranchName()}")
    mgr.addOperation("Error: Search Part")
    
    # 6. End Logic
    mgr.addEnd()
    
    print("\n--- Generated DSL ---")
    print(mgr.getDSL())
    
    print("\nSUCCESS: Manager logic executed without errors.")

if __name__ == "__main__":
    testManagerLogic()