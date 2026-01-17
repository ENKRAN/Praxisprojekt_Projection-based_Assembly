import numpy as np
from app.core.math_utils import computeSVGToTagMatrix
from app.core.domain import InstructionContent, PoseData

def testEverything():
    print("--- Testing Math Utils ---")
    # Dummy Homography (Identity matrix)
    dummy_H = np.eye(3)
    tag_size = 0.038
    
    result_matrix = computeSVGToTagMatrix(dummy_H, tag_size)
    print("Matrix calculated:")
    print(result_matrix)
    
    print("\n--- Testing Domain Objects ---")
    # Test Dataclass
    pose = PoseData(matrix_data=[1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1])
    content = InstructionContent(
        step_id="step_1",
        image_path="test.png",
        svg_path="test.svg",
        reference_tag_pose=pose
    )
    
    print(f"Content created: {content.step_id}")
    print(f"Numpy conversion: \n{content.reference_tag_pose.toNumpy()}")
    print("\nSUCCESS: Setup is correct!")

if __name__ == "__main__":
    testEverything()