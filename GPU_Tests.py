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
        """
        Does the actual rendering each frame.
        """
        glClear(GL_COLOR_BUFFER_BIT | GL_STENCIL_BUFFER_BIT)
        
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        
        fov_degrees = 65.5
        z_near = 1.0
        z_far = 1000.0
        
        w = self.width()
        h = self.height()
        if h == 0: h = 1
        aspect_ratio = w / h
        
        fov_radians = math.radians(fov_degrees)
        t = z_near * math.tan(fov_radians / 2)
        b = -t
        r = t * aspect_ratio
        l = -r
        
        glFrustum(l, r, b, t, z_near, z_far)
        
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        glTranslatef(0, 0, -400)
        
        glRotatef(self.angle, 0, 1, 0) 
        glRotatef(15, 1, 0, 0)
        
        glTranslatef(-300, -300, 0)


        for pathObj in self.pathObjs:            
            # Stencil Schritt
            glStencilFillPathNV(pathObj, GL_COUNT_UP_NV, 0x1F)
            
            # Cover Schritt
            glEnable(GL_STENCIL_TEST)
            glStencilFunc(GL_NOTEQUAL, 0, 0x1F)
            glStencilOp(GL_KEEP, GL_KEEP, GL_ZERO) # Setzt Stencil danach zurück auf 0!
            
            glColor3f(1, 1, 0) # Gelb
            glCoverFillPathNV(pathObj, GL_BOUNDING_BOX_NV)
            
            # --- B. STROKE (Rand) ---
            
            # Einstellungen (siehe Tipp unten: Besser in initializeGL)
            glPathParameterfNV(pathObj, GL_PATH_STROKE_WIDTH_NV, 5.0)
            glPathParameteriNV(pathObj, GL_PATH_JOIN_STYLE_NV, GL_ROUND_NV)

            # Stencil für Stroke
            glStencilStrokePathNV(pathObj, 0x1, ~0)

            # Cover für Stroke
            glColor3f(1.0, 1.0, 1.0) # Weiß
            glStencilFunc(GL_EQUAL, 0x1, 0x1)
            glStencilOp(GL_KEEP, GL_KEEP, GL_ZERO)
            
            glCoverStrokePathNV(pathObj, GL_CONVEX_HULL_NV)

        # --- 3. NACHBEREITUNG ---
        glDisable(GL_STENCIL_TEST)
        
        # Animation für den nächsten Frame vorbereiten
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

    fmt.setSamples(8) 
    
    QSurfaceFormat.setDefaultFormat(fmt)

    svgPathString = b"M300 200 A100 100 0 1 0 300 400 A100 100 0 1 0 300 200"
    
    window = QMainWindow()
    widget = PathRenderingWidget(svg_path=svgPathString)
    window.setCentralWidget(widget)
    window.resize(1280, 720)
    window.show()
    
    sys.exit(app.exec())