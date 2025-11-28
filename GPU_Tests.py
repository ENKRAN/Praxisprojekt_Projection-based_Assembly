import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QTimer
import math
from src.setup import get_calibration_data

# OpenGL Imports
from OpenGL.GL import *
# Import the Nvidia Extension functions
from OpenGL.GL.NV.path_rendering import *

from src.setup import get_calibration_data

class PathRenderingWidget(QOpenGLWidget):
    def __init__(self, num_paths=1, svg_path=None, parent=None):
        super().__init__(parent)
        self.num_paths = num_paths
        self.svg_path = svg_path
        self.pathObjs = [] 

    def initializeGL(self):
        """Initialize everything once here."""
        """calibration_data_path = 'data/projector_camera_calibration/calibration.yml'
        cam_K, cam_kc, proj_K, proj_kc, R, T = get_calibration_data(calibration_data_path)

        print(f"Camera Intrinsics (Shape: {cam_K.shape}):\n{cam_K}")
        print(f"Camera Distortion Coefficients (Shape: {cam_kc.shape}):\n{cam_kc}")
        print(f"Projector Intrinsics (Shape: {proj_K.shape}):\n{proj_K}")
        print(f"Projector Distortion Coefficients (Shape: {proj_kc.shape}):\n{proj_kc}")
        print(f"Rotation Matrix (Shape: {R.shape}):\n{R}")
        print(f"Translation Vector (Shape: {T.shape}):\n{T}")"""

        if not self.checkSupport():
            return

        # Background color (dark gray)
        glClearColor(0.0, 0.0, 0.0, 1.0)

        # For MXAA (Multisample Anti-Aliasing)
        glEnable(GL_MULTISAMPLE)
        
        base_id = glGenPathsNV(self.num_paths)

        # Store all path IDs in order to use them later
        self.pathObjs = [base_id + i for i in range(self.num_paths)]

        print("Generated Path IDs:", self.pathObjs)
    
        for path_id in self.pathObjs:
            glPathStringNV(path_id, GL_PATH_FORMAT_SVG_NV, len(self.svg_path), self.svg_path)

        # Timer for animation (so we can see the 3D rotation)
        self.angle = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update) # Calls paintGL
        self.timer.start(16) # approx. 60 FPS

    def checkSupport(self):
        # First test what context we actually have
        version = glGetString(GL_VERSION)
        vendor = glGetString(GL_VENDOR)
        renderer = glGetString(GL_RENDERER)
        print(f"OpenGL Version: {version}")
        print(f"Vendor: {vendor}") # Should be "NVIDIA Corporation"
        print(f"Renderer: {renderer}")

        # Check if the extension was loaded
        num_extensions = glGetIntegerv(GL_NUM_EXTENSIONS)
        has_nv_path = False
        
        for i in range(num_extensions):
            ext_name = glGetStringi(GL_EXTENSIONS, i)
            if ext_name == b"GL_NV_path_rendering":
                has_nv_path = True
                break
                
        if not has_nv_path:
            print("ERROR: GL_NV_path_rendering is not supported by this driver/context!")
            return False
        else:   
            print("GL_NV_path_rendering is supported.")
            return True

    def paintGL(self):
        """Draw every frame here."""
        for pathObj in self.pathObjs:
            # IMPORTANT: Stencil buffer must also be cleared
            glClear(GL_COLOR_BUFFER_BIT | GL_STENCIL_BUFFER_BIT)
            
            # --- PROJECTION MATRIX BASED ON ANGLE ---
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            
            fov_degrees = 65.5  # opening angle (phi)
            z_near = 1.0        # n
            z_far = 1000.0      # f
            
            w = self.width()
            h = self.height()
            if h == 0: h = 1
            aspect_ratio = w / h
            
            # t = n * tan(phi / 2)
            fov_radians = math.radians(fov_degrees)
            t = z_near * math.tan(fov_radians / 2)
            
            # b = -t (symmetry, as in the image b = -n * tan(...))
            b = -t
            
            r = t * aspect_ratio
            l = -r
            
            # Parameters: left, right, bottom, top, near, far
            glFrustum(l, r, b, t, z_near, z_far)
            
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()

            # Move camera back a bit
            glTranslatef(0, 0, -400)
            
            # Rotate the object in 3D space
            glRotatef(self.angle, 0, 1, 0) # Rotation around Y-axis
            glRotatef(15, 1, 0, 0)         # Slightly tilt backwards
            
            # Shift the path so it rotates in the middle (it is defined at 300,300 in the SVG)
            glTranslatef(-300, -300, 0)

            # --- RENDERING STEPS (Stencil then Cover) ---
            
            # Step A: Stencil (create template)
            # Counts up in the stencil buffer, analogous to the PDF [cite: 89]
            glStencilFillPathNV(pathObj, GL_COUNT_UP_NV, 0x1F)
            
            # Step B: Cover (apply color)
            # Enable the stencil test
            glEnable(GL_STENCIL_TEST)
            glStencilFunc(GL_NOTEQUAL, 0, 0x1F)
            glStencilOp(GL_KEEP, GL_KEEP, GL_ZERO)
            
            # Set color (yellow as in the PDF example)
            glColor3f(1, 1, 0)
            
            # Draw! "Cover" fills everything where stencil != 0
            glCoverFillPathNV(pathObj, GL_BOUNDING_BOX_NV)

            glCoverFillPathNV(pathObj, GL_BOUNDING_BOX_NV)

            # --- NEW: STROKE (OUTLINE) ---
            
            # 1. Set brush settings
            # Width of the stroke (in coordinate units)
            glPathParameterfNV(pathObj, GL_PATH_STROKE_WIDTH_NV, 5.0)
            # Round corners at line connections (looks better for heart)
            glPathParameteriNV(pathObj, GL_PATH_JOIN_STYLE_NV, GL_ROUND_NV)

            # 2. Calculate stencil for the stroke
            # We use the stencil buffer again, set the reference bit to 1
            # 0x1 = mask, ~0 = mask for inversion (all bits on)
            glStencilStrokePathNV(pathObj, 0x1, ~0)

            # 3. Cover stroke (draw the color)
            glColor3f(1.0, 1.0, 1.0) # White
            # We only draw where the stencil value was set by step 2
            glStencilFunc(GL_EQUAL, 0x1, 0x1)
            glStencilOp(GL_KEEP, GL_KEEP, GL_ZERO) # Clean up afterwards
            
            glCoverStrokePathNV(pathObj, GL_CONVEX_HULL_NV)
            
            glDisable(GL_STENCIL_TEST)
            
            # Continue rotating animation
            self.angle += 1

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

# Standard PyQt boilerplate
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    from PyQt6.QtGui import QSurfaceFormat
    fmt = QSurfaceFormat()
    
    fmt.setStencilBufferSize(8)
    
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)

    fmt.setSamples(16) 
    
    QSurfaceFormat.setDefaultFormat(fmt)

    svgPathString = b"M300 200 A100 100 0 1 0 300 400 A100 100 0 1 0 300 200"
    
    window = QMainWindow()
    widget = PathRenderingWidget(svg_path=svgPathString)
    window.setCentralWidget(widget)
    window.resize(1280, 720)
    window.show()
    
    sys.exit(app.exec())