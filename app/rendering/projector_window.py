import numpy as np
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import pyqtSlot
from OpenGL.GL import *
from OpenGL.GL.NV.path_rendering import *

# Make sure you moved svg_manipulation.py to app/utils/svg_loader.py
from app.utils.svg_utils import convertSVGElementsToBytePaths, convertSVGElementsToBytePathsFromString
from app.utils.math_utils import computeSVGToTagMatrix, buildExtrinsicMatrix
from app.core.config import Config
from app.core.user_settings import UserSettings

class PathRenderingWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Load Calibration once
        calib = Config.getCalibration()
        self.projector_intrinsics = calib.proj_k
        self.camera_intrinsics = calib.cam_k
        
        # Extrinsics Projector -> Camera (from Config)
        self.T_proj_cam = buildExtrinsicMatrix(calib.R, calib.T)
        
        # Scale Translation (mm -> m) as in your legacy code
        self.T_proj_cam[0, 3] /= 1000.0
        self.T_proj_cam[1, 3] /= 1000.0
        self.T_proj_cam[2, 3] /= 1000.0

        self.path_objs = []
        self.svg_elements = []
        self.is_baked = False
        self.tag_size = UserSettings.get_tag_size()

        self.current_tag_pose = np.eye(4, dtype=np.float32)
        self.M_svg_to_tag = np.eye(4, dtype=np.float32)

        # AI Mode Nudge / Manual Offset
        self.ai_offset = np.zeros(3, dtype=np.float32)

        # No Tag mode (no AprilTag, still 3D projection)
        self._no_tag_mode = False
        self._viewport_w = 1280
        self._viewport_h = 720
        self._nv_supported = False  # set True in initializeGL if extension found
        self._trace_pending = False
        self._trace_pixels = []

    def setTagSize(self, size: float):
        self.tag_size = size
        print(f"Projector: Tag size updated to {self.tag_size}")

    def setAIOffset(self, dx: float, dy: float, dz: float):
        """Manually nudge the projection in AI mode (meters)."""
        self.ai_offset = np.array([dx, dy, dz], dtype=np.float32)
        print(f"Projector: AI Offset updated: {self.ai_offset}")
        self.update()

    def initializeGL(self):
        # ... (rest of initializeGL) ...
        if not self.checkSupport():
            print("CRITICAL ERROR: NV_path_rendering not supported on this GPU. Projection will not work.")
            self._nv_supported = False
            return

        self._nv_supported = True
        glClearColor(0.0, 0.0, 0.0, 1.0) # Black background
        glEnable(GL_MULTISAMPLE)         # Enable Anti-Aliasing (MSAA)

    def checkSupport(self):
        try:
            num_extensions = glGetIntegerv(GL_NUM_EXTENSIONS)
            for i in range(num_extensions):
                ext_name = glGetStringi(GL_EXTENSIONS, i)
                if ext_name == b"GL_NV_path_rendering":
                    return True
            return False
        except Exception as e:
            print(f"OpenGL Init Error: {e}")
            return False

    def loadSvg(self, svg_path):
        # ... (rest of loadSvg) ...
        self.makeCurrent() # Ensure context is active
        
        # Clean up old paths
        if self.path_objs:
            glDeletePathsNV(self.path_objs[0], len(self.path_objs))
            self.path_objs = []

        if not svg_path:
            self.svg_elements = []
            self.is_baked = False
            self._no_tag_mode = False
            self.update()
            return

        # Parse SVG using existing logic
        self.svg_elements = convertSVGElementsToBytePaths(svg_path)
        num_paths = len(self.svg_elements)
        print(f"Loaded SVG with {num_paths} paths.")

        if num_paths > 0:
            base_id = glGenPathsNV(num_paths)
            self.path_objs = [base_id + i for i in range(num_paths)]

            for path_id, element in zip(self.path_objs, self.svg_elements):
                svg_bytes = element['svg_path_string']
                glPathStringNV(path_id, GL_PATH_FORMAT_SVG_NV, len(svg_bytes), svg_bytes)

                # Set path parameters
                glPathParameterfNV(path_id, GL_PATH_STROKE_WIDTH_NV, element['stroke_width'])
                glPathParameteriNV(path_id, GL_PATH_JOIN_STYLE_NV, GL_ROUND_NV)
                glPathParameteriNV(path_id, GL_PATH_END_CAPS_NV, GL_ROUND_NV)
        
        self.doneCurrent()
        self.update()

    def loadSvgFromString(self, svg_string: str):
        # ... (rest of loadSvgFromString) ...
        self.makeCurrent() # Ensure context is active
        
        # Clean up old paths from memory
        if self.path_objs:
            glDeletePathsNV(self.path_objs[0], len(self.path_objs))
            self.path_objs = []

        if not svg_string:
            self.svg_elements = []
            self.is_baked = False
            self.update()
            return

        # Parse SVG dynamically
        self.svg_elements = convertSVGElementsToBytePathsFromString(svg_string)
        num_paths = len(self.svg_elements)
        print(f"[Projector] SVG parsed: {num_paths} renderable path(s) from {len(svg_string)} char string.")
        if num_paths == 0:
            print("[Projector] WARNING: SVG contained no renderable paths — check element types and stroke/fill attributes.")

        if num_paths > 0:
            base_id = glGenPathsNV(num_paths)
            self.path_objs = [base_id + i for i in range(num_paths)]

            for path_id, element in zip(self.path_objs, self.svg_elements):
                svg_bytes = element['svg_path_string']
                glPathStringNV(path_id, GL_PATH_FORMAT_SVG_NV, len(svg_bytes), svg_bytes)

                # Set path parameters
                glPathParameterfNV(path_id, GL_PATH_STROKE_WIDTH_NV, element['stroke_width'])
                glPathParameteriNV(path_id, GL_PATH_JOIN_STYLE_NV, GL_ROUND_NV)
                glPathParameteriNV(path_id, GL_PATH_END_CAPS_NV, GL_ROUND_NV)
        
        self.doneCurrent()
        self.update()

    def resizeGL(self, w, h):
        """
        Sets up the projection matrix based on projector intrinsics, 
        scaled to the current window size.
        """
        self._viewport_w = w
        self._viewport_h = h
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        
        # Scaling factor: calibration was likely done at 1280x720
        # If window is different, we MUST scale fx, fy, cx, cy.
        scale_x = w / 1280.0
        scale_y = h / 720.0

        fx = self.projector_intrinsics[0, 0] * scale_x
        fy = self.projector_intrinsics[1, 1] * scale_y
        cx = self.projector_intrinsics[0, 2] * scale_x
        cy = self.projector_intrinsics[1, 2] * scale_y
        
        z_near = 0.1
        z_far = 1000.0
        
        # Calculate frustum (off-axis projection)
        l = -cx * z_near / fx
        r = (w - cx) * z_near / fx
        b = -(h - cy) * z_near / fy
        t = cy * z_near / fy
        
        glFrustum(l, r, b, t, z_near, z_far)
        glMatrixMode(GL_MODELVIEW)
    
    @pyqtSlot(np.ndarray, np.ndarray, int)
    def setBakingMatrix(self, homography, color_img, tag_id):
        # ... (rest of setBakingMatrix) ...
        print("Projector: Baking Matrix updated.")
        self.M_svg_to_tag = computeSVGToTagMatrix(homography, self.tag_size)

        # DIAGNOSTIC: verify physical positions of key SVG pixels
        H = homography
        # Tag center in camera pixels (from H @ [0,0,1])
        c = H @ np.array([0.0, 0.0, 1.0])
        tag_cx, tag_cy = c[0] / c[2], c[1] / c[2]
        # Tag corner (+1,+1) in camera pixels
        corner = H @ np.array([1.0, 1.0, 1.0])
        corner_px = corner[0] / corner[2], corner[1] / corner[2]
        print(f"[DIAG BAKE] tag_size={self.tag_size}m, scale_factor={self.tag_size/2:.4f}m")
        print(f"[DIAG BAKE] Tag center pixel: ({tag_cx:.1f}, {tag_cy:.1f})")
        print(f"[DIAG BAKE] Tag (+1,+1) corner pixel: ({corner_px[0]:.1f}, {corner_px[1]:.1f})")
        for label, (u, v) in [("tag_center", (tag_cx, tag_cy)), ("tag_corner(+1,+1)", corner_px)]:
            p = self.M_svg_to_tag @ np.array([u, v, 0.0, 1.0])
            px, py = p[0] / p[3] * 1000, p[1] / p[3] * 1000
            print(f"[DIAG BAKE]   SVG pixel ({u:.1f},{v:.1f}) -> physical ({px:.1f}mm, {py:.1f}mm) — expected tag_corner=(±{self.tag_size/2*1000:.1f}mm)")

        self.is_baked = True
        self._trace_pixels = [(tag_cx, tag_cy, "center"), (corner_px[0], corner_px[1], "corner(+1,+1)")]
        self._trace_pending = True

        # DIAGNOSTIC: project crosses at exact tag center + corner pixels to verify rendering pipeline
        # Red cross = tag center, Blue cross = tag corner (+1,+1)
        # If both land on physical tag corners -> pipeline correct; user drawing was too large
        r = 12
        cx_x, cx_y = tag_cx, tag_cy
        co_x, co_y = corner_px[0], corner_px[1]
        diag_svg = (
            f'<svg viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
            f'<path d="M {cx_x-r:.1f} {cx_y:.1f} L {cx_x+r:.1f} {cx_y:.1f} M {cx_x:.1f} {cx_y-r:.1f} L {cx_x:.1f} {cx_y+r:.1f}" '
            f'stroke="#ff0000" stroke-width="4" fill="none"/>'
            f'<path d="M {co_x-r:.1f} {co_y:.1f} L {co_x+r:.1f} {co_y:.1f} M {co_x:.1f} {co_y-r:.1f} L {co_x:.1f} {co_y+r:.1f}" '
            f'stroke="#0000ff" stroke-width="4" fill="none"/>'
            f'</svg>'
        )
        print(f"[DIAG BAKE] Loading diagnostic SVG: red cross at center ({cx_x:.1f},{cx_y:.1f}), blue cross at corner ({co_x:.1f},{co_y:.1f})")
        self.loadSvgFromString(diag_svg)
        self.update()

    @pyqtSlot(np.ndarray, np.ndarray, int)
    def updateTagPose(self, R_ct, tvec, tag_id):
        # ... (rest of updateTagPose) ...
        new_pose = buildExtrinsicMatrix(R_ct, tvec)
        self.current_tag_pose = new_pose
        
        if self.is_baked:
            self.update()
    
    @pyqtSlot(float, float, float, float)
    def updateTablePlane(self, a, b, c, d):
        """
        Called by VisionWorker to update the virtual table plane for AI Mode.
        Calculates a projective matrix (Homography) from SVG pixels to the plane.
        """
        # print(f"[Plane] n=({a:.3f},{b:.3f},{c:.3f}), d={d:.3f}, table_depth≈{-d/c:.3f}m")
        
        if not self._no_tag_mode:
            return

        # Plane normal n = [a, b, c], distance d
        # For pixel p = [u, v, 1]^T, 3D point P = s * K_inv * p
        # n * P + d = 0  =>  s = -d / (n * K_inv * p)
        
        n = np.array([a, b, c])
        K_inv = np.linalg.inv(self.camera_intrinsics)
        
        M = np.zeros((4, 4), dtype=np.float32)
        M[0:3, 0:3] = K_inv * (-d)
        w_row = n @ K_inv
        M[3, 0:3] = w_row
        M[3, 3] = 0.0 
        
        M_final = np.zeros((4, 4), dtype=np.float32)
        M_final[:, 0] = M[:, 0] # u
        M_final[:, 1] = M[:, 1] # v
        M_final[:, 3] = M[:, 2] # the constant '1' part of the pixel coord
        
        # Apply Nudge / Manual Offset in Camera Space
        if np.any(self.ai_offset):
             # To apply translation after unprojection: P' = P + Offset
             # In homogeneous terms: T_offset * M_final
             T_off = np.eye(4, dtype=np.float32)
             T_off[0, 3] = self.ai_offset[0]
             T_off[1, 3] = self.ai_offset[1]
             T_off[2, 3] = self.ai_offset[2]
             M_final = T_off @ M_final

        self.M_svg_to_tag = M_final
        self.is_baked = True
        self.update()

    def setNoTagMode(self, enabled: bool):
        # ... (rest of setNoTagMode) ...
        self._no_tag_mode = enabled
        self.update()

    def paintGL(self):
        # ... (rest of paintGL) ...
        glClearStencil(0)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glStencilMask(~0)
        glClear(GL_COLOR_BUFFER_BIT | GL_STENCIL_BUFFER_BIT)

        if not self._nv_supported or not self.is_baked or not self.path_objs:
            return

        # One-shot 3D trace after each bake to verify transform chain
        if self._trace_pending and not self._no_tag_mode:
            self._trace_pending = False
            for u, v, lbl in getattr(self, '_trace_pixels', []):
                p0 = np.array([u, v, 0.0, 1.0], dtype=np.float64)
                p1 = self.M_svg_to_tag.astype(np.float64) @ p0
                p2 = self.current_tag_pose.astype(np.float64) @ p1
                p3 = self.T_proj_cam.astype(np.float64) @ p2
                tag_phys = p1[:3] / p1[3]
                cam_phys = p2[:3] / p2[3]
                proj_phys = p3[:3] / p3[3]
                fx_p = float(self.projector_intrinsics[0, 0])
                cx_p = float(self.projector_intrinsics[0, 2])
                proj_px = fx_p * proj_phys[0] / proj_phys[2] + cx_p
                print(f"[TRACE {lbl}] tag_local={tag_phys*1000} mm")
                print(f"[TRACE {lbl}] cam_space={cam_phys*1000} mm  (z={cam_phys[2]*1000:.1f}mm)")
                print(f"[TRACE {lbl}] proj_space z={proj_phys[2]*1000:.1f}mm  proj_px_x={proj_px:.1f}")

        glLoadIdentity()
        glScale(1.0, -1.0, -1.0)  # Flip Y and Z for OpenGL coordinate system

        # Chain transformations: Projector -> Camera -> Tag -> SVG
        glMultMatrixf(self.T_proj_cam.T)
        if not self._no_tag_mode:
            glMultMatrixf(self.current_tag_pose.T)
        glMultMatrixf(self.M_svg_to_tag.T)

        # Rendering Loop using NV_path_rendering stencil & cover
        for path_obj, element in zip(self.path_objs, self.svg_elements):     
            if element['is_filled']:
                glStencilFillPathNV(path_obj, GL_COUNT_UP_NV, 0x1F)
                glEnable(GL_STENCIL_TEST)
                glStencilFunc(GL_NOTEQUAL, 0, 0x1F)
                glStencilOp(GL_KEEP, GL_KEEP, GL_ZERO)
                glColor3f(*element['fill_color'])
                glCoverFillPathNV(path_obj, GL_BOUNDING_BOX_NV)
                glDisable(GL_STENCIL_TEST)

            if element['stroke_color'] is not None:
                glStencilStrokePathNV(path_obj, 0x1, ~0)
                glEnable(GL_STENCIL_TEST)
                glColor3f(*element['stroke_color'])
                glStencilFunc(GL_EQUAL, 0x1, 0x1)
                glStencilOp(GL_KEEP, GL_KEEP, GL_ZERO)
                glCoverStrokePathNV(path_obj, GL_CONVEX_HULL_NV)
                glDisable(GL_STENCIL_TEST)


class ProjectorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Projector Output")
        self.setStyleSheet("background-color: black;")
        
        self.gl_widget = PathRenderingWidget(self)
        self.setCentralWidget(self.gl_widget)
        
    def loadInstruction(self, svg_path):
        """Public API to load an instruction."""
        print(f"Loading instruction from: {svg_path}")
        self.gl_widget.loadSvg(svg_path)

    def loadInstructionFromString(self, svg_string: str):
        """Public API to load an instruction dynamically from a string."""
        self.gl_widget.loadSvgFromString(svg_string)

    def loadInstructionWithoutTag(self, svg_string: str):
        """Load SVG as a flat 2D screen overlay (no AprilTag / homography needed)."""
        self.gl_widget.loadSvgFromString(svg_string)
        self.gl_widget.setNoTagMode(True)

    def clearProjection(self):
        """Public API to clear the screen."""
        self.gl_widget.loadSvg(None)

    def setTagSize(self, size: float):
        """Public API to update the tag size."""
        self.gl_widget.setTagSize(size)