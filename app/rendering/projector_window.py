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

class PathRenderingWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Load Calibration once
        calib = Config.getCalibration()
        self.projector_intrinsics = calib.proj_k
        
        # Extrinsics Projector -> Camera (from Config)
        self.T_proj_cam = buildExtrinsicMatrix(calib.R, calib.T)
        
        # Scale Translation (mm -> m) as in your legacy code
        self.T_proj_cam[0, 3] /= 1000.0
        self.T_proj_cam[1, 3] /= 1000.0
        self.T_proj_cam[2, 3] /= 1000.0

        self.path_objs = [] 
        self.svg_elements = []
        self.is_baked = False
        self.tag_size = 0.038 # Default, can be updated via setter

        self.current_tag_pose = np.eye(4, dtype=np.float32)
        self.M_svg_to_tag = np.eye(4, dtype=np.float32) 

    def initializeGL(self):
        """Initializes OpenGL context and checks for NV_path_rendering support."""
        if not self.checkSupport():
            print("CRITICAL ERROR: NV_path_rendering not supported on this GPU.")
            return

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
        """
        Loads a new SVG file and prepares OpenGL paths.
        
        Args:
            svg_path (str): Path to the SVG file. If None, clears existing paths.
        """
        self.makeCurrent() # Ensure context is active
        
        # Clean up old paths
        if self.path_objs:
            glDeletePathsNV(self.path_objs[0], len(self.path_objs))
            self.path_objs = []

        if not svg_path:
            self.svg_elements = []
            self.is_baked = False
            self.update()
            return

        # Parse SVG using existing logic
        self.svg_elements = convertSVGElementsToBytePaths(svg_path)
        num_paths = len(self.svg_elements)

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
        """
        Loads a new SVG string directly into OpenGL paths without reading from disk.
        
        Args:
            svg_string (str): Raw SVG XML string.
        """
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
        Sets up the projection matrix based on projector intrinsics.
        
        Args:
            w (int): Width of the viewport.
            h (int): Height of the viewport.
        """
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        
        fx = self.projector_intrinsics[0, 0]
        fy = self.projector_intrinsics[1, 1]
        cx = self.projector_intrinsics[0, 2]
        cy = self.projector_intrinsics[1, 2]
        
        z_near = 0.1
        z_far = 10000.0
        
        # Calculate frustum (off-axis projection)
        l = -cx * z_near / fx
        r = (w - cx) * z_near / fx
        b = -(h - cy) * z_near / fy
        t = cy * z_near / fy
        
        glFrustum(l, r, b, t, z_near, z_far)
        glMatrixMode(GL_MODELVIEW)
    
    @pyqtSlot(np.ndarray, np.ndarray, int)
    def setBakingMatrix(self, homography, color_img, tag_id):
        """
        Called when Snapshot is taken. Computes the fixed relation SVG <-> Tag.
        
        Args:
            homography (np.ndarray): 3x3 homography matrix from tag to projector image
            color_img (np.ndarray): Color image (not used here but could be for debugging)
        """
        print("Projector: Baking Matrix updated.")
        self.M_svg_to_tag = computeSVGToTagMatrix(homography, self.tag_size)
        self.is_baked = True
        self.update()

    @pyqtSlot(np.ndarray, np.ndarray, int)
    def updateTagPose(self, R_ct, tvec, tag_id):
        """
        Called every frame by VisionWorker to move the projection.
        
        Args:
            R_ct (np.ndarray): 3x3 rotation matrix from camera to tag
            tvec (np.ndarray): 3x1 translation vector from camera to tag
        """
        new_pose = buildExtrinsicMatrix(R_ct, tvec)
        self.current_tag_pose = new_pose
        
        if self.is_baked:
            self.update()
    
    def paintGL(self):
        """Render loop."""
        glClearStencil(0)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glStencilMask(~0)
        glClear(GL_COLOR_BUFFER_BIT | GL_STENCIL_BUFFER_BIT)

        if not self.is_baked or not self.path_objs:
            return

        glLoadIdentity()
        glScale(1.0, -1.0, -1.0) # Flip Y and Z for OpenGL coordinate system
        
        # Chain transformations: Projector -> Camera -> Tag -> SVG
        glMultMatrixf(self.T_proj_cam.T)
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
        self.gl_widget.loadSvg(svg_path)

    def loadInstructionFromString(self, svg_string: str):
        """Public API to load an instruction dynamically from a string."""
        self.gl_widget.loadSvgFromString(svg_string)
        
    def clearProjection(self):
        """Public API to clear the screen."""
        self.gl_widget.loadSvg(None)