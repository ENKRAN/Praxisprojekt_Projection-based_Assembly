import numpy as np

def computeSVGToTagMatrix(homography: np.ndarray, tag_size_meters: float) -> np.ndarray:
        """
        Calculates the Transformation Matrix from SVG user units (same as pixels in image (1280x720)) to Physical Tag Plane.
        
        Args:
            homography: The 3x3 homography matrix from the library (Ideal Tag [-1,1] -> Pixel).
            tag_size_meters: The physical size of the tag (e.g. 0.05).
        Returns:
            A 4x4 transformation matrix mapping SVG coordinates to the physical tag plane.
        """
        # 1. Access the raw homography (Ideal Tag [-1,1] -> Pixel)
        H_lib = homography
        
        # 2. Invert (Pixel -> Ideal Tag [-1,1])
        try:
            H_inv = np.linalg.inv(H_lib)
        except np.linalg.LinAlgError:
            print("Error: Homography matrix is singular!")
            return np.identity(4)
        
        # 3. Scaling from "Ideal" (-1 to 1) to "Metric" (-size/2 to size/2)
        # We multiply H_inv from the left with the scaling matrix.
        # Since H_inv maps [u, v, 1]^T to [x_ideal, y_ideal, w]^T,
        # we simply scale x and y by (tag_size / 2).
        
        scale_factor = tag_size_meters / 2.0
        
        # We scale the first two rows of H_inv
        H_phys_inv = H_inv.copy()
        H_phys_inv[0, :] *= scale_factor
        H_phys_inv[1, :] *= scale_factor
        # The 3rd row (homogeneous coordinate w) remains unchanged!
        
        # 4. "Baking" into 4x4 matrix (for OpenGL/SVG/Rendering)
        # The format is identical to your previous code.
        M_baking = np.eye(4, dtype=np.float32)
        
        # Rotation / Scaling / Shearing part (2x2 top left)
        M_baking[0, 0] = H_phys_inv[0, 0]
        M_baking[0, 1] = H_phys_inv[0, 1]
        M_baking[1, 0] = H_phys_inv[1, 0]
        M_baking[1, 1] = H_phys_inv[1, 1]
        
        # Translation part (Column 3 in your notation, index 3 at 0-based)
        # Note: In your original code, you mapped H_inv[0, 2] to M[0, 3].
        # That is correct for the translation in 2D space.
        M_baking[0, 3] = H_phys_inv[0, 2]
        M_baking[1, 3] = H_phys_inv[1, 2]
        
        # Homogeneous coordinate row (Important for perspective division)
        # This row ensures that (u,v) is projected correctly.
        M_baking[3, 0] = H_phys_inv[2, 0]
        M_baking[3, 1] = H_phys_inv[2, 1]
        M_baking[3, 3] = H_phys_inv[2, 2]
        
        return M_baking

def buildExtrinsicMatrix(R: np.ndarray, T: np.ndarray) -> np.ndarray:
    """
    Builds the 4x4 extrinsic matrix from a rotation matrix (3x3) and a translation vector.
    
    Args:
        R: 3x3 Rotation matrix.
        T: Translation vector (3x1 or flattened).
        
    Returns:
        4x4 Extrinsic matrix (float32).
    """
    matrix = np.eye(4, dtype=np.float32)
    
    # Rotation matrix in the top-left 3x3 part
    matrix[:3, :3] = R
    
    # Translation in the right column
    # .flatten() ensures that T is a vector, regardless of shape (3,1) or (3,)
    matrix[:3, 3] = T.flatten() 
    
    return matrix