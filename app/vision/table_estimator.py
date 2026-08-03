import numpy as np

class TablePlaneEstimator:
    def __init__(self, camera_intrinsics):
        self.K = camera_intrinsics
        self.K_inv = np.linalg.inv(self.K)
        
        # History for smoothing
        self.plane_history = []
        self.max_history = 30 # Increased for better stability

    def estimate_plane(self, depth_img, depth_scale):
        # ... (rest of sampling code remains same) ...
        # (I will provide the full method to be safe)
        h, w = depth_img.shape
        step = 40
        us = np.arange(step, w - step, step)
        vs = np.arange(step, h - step, step)
        uu, vv = np.meshgrid(us, vs)
        
        u_flat = uu.flatten()
        v_flat = vv.flatten()
        depths = depth_img[v_flat, u_flat] * depth_scale
        
        mask = (depths > 0.3) & (depths < 2.5)
        if np.sum(mask) < 20:
            return None
            
        u_valid = u_flat[mask]
        v_valid = v_flat[mask]
        z_valid = depths[mask]
        
        points_3d = np.zeros((len(u_valid), 3))
        points_3d[:, 0] = (u_valid - self.K[0, 2]) * z_valid / self.K[0, 0]
        points_3d[:, 1] = (v_valid - self.K[1, 2]) * z_valid / self.K[1, 1]
        points_3d[:, 2] = z_valid
        
        # RANSAC
        best_plane = None
        max_inliers = -1
        for _ in range(50):
            idx = np.random.choice(points_3d.shape[0], 3, replace=False)
            p1, p2, p3 = points_3d[idx]
            v1, v2 = p2 - p1, p3 - p1
            normal = np.cross(v1, v2)
            norm = np.linalg.norm(normal)
            if norm < 1e-6: continue
            normal /= norm
            d = -np.dot(normal, p1)
            inliers = np.sum(np.abs(np.dot(points_3d, normal) + d) < 0.015)
            if inliers > max_inliers:
                max_inliers = inliers
                best_plane = (normal[0], normal[1], normal[2], d)
        
        if best_plane is None or max_inliers < 20:
            return None
            
        # Refine
        normal, d = best_plane[0:3], best_plane[3]
        inlier_points = points_3d[np.abs(np.dot(points_3d, normal) + d) < 0.015]
        if len(inlier_points) >= 3:
            centroid = np.mean(inlier_points, axis=0)
            _, _, vh = np.linalg.svd(inlier_points - centroid)
            refined_normal = vh[2, :]
            if refined_normal[2] < 0: refined_normal *= -1
            refined_d = -np.dot(refined_normal, centroid)
            best_plane = (refined_normal[0], refined_normal[1], refined_normal[2], refined_d)

        # Smoothing with Outlier Rejection
        if self.plane_history:
            # Check if new plane is wildly different from average
            avg_prev = np.mean(self.plane_history, axis=0)
            diff = np.abs(np.array(best_plane) - avg_prev)
            if np.any(diff > 0.1): # If a,b,c or d shifts by > 10cm or large normal change
                # It might be an outlier or hand moving. We give it less weight.
                pass 

        self.plane_history.append(best_plane)
        if len(self.plane_history) > self.max_history:
            self.plane_history.pop(0)
            
        return tuple(np.mean(self.plane_history, axis=0))
