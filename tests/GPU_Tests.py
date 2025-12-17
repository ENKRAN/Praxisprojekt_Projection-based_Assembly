import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import pyqtSlot, Qt
from PyQt6.QtGui import QSurfaceFormat, QPixmap, QImage

from OpenGL.GL import *
from OpenGL.GL.NV.path_rendering import *

from tests.svg_manipulation import convertSVGElementsToBytePaths
from src.setup import get_calibration_data
from src.setup import buildExtrinsicMatrix
from tests.apriltag_tests import WebcamThread
from src.apriltag_detection import AprilTagDetector


class PathRenderingWidget(QOpenGLWidget):
    def __init__(self, svg_converted_elements, projector_intrinsics, T_proj_cam, 
                 initial_tag_pose, camera_intrinsics, parent=None):
        super().__init__(parent)
        self.num_paths = len(svg_converted_elements) if svg_converted_elements is not None else 0
        self.svg_converted_elements = svg_converted_elements
        self.projector_intrinsics = projector_intrinsics
        self.pathObjs = [] 

        self.T_proj_cam = T_proj_cam
        
        # IMPORTANT: We only scale the translation (column 3) from mm to m
        self.T_proj_cam[0, 3] /= 1000.0
        self.T_proj_cam[1, 3] /= 1000.0
        self.T_proj_cam[2, 3] /= 1000.0

        self.current_tag_pose = initial_tag_pose

        self.M_svg_to_tag = self.computeSVGToTagMatrixAnalytic(camera_intrinsics, initial_tag_pose)

    def initializeGL(self):
        """
        Initialize everything once here.
        This is called once when the window is created.
        """
        
        # 1. Check if NV_path_rendering is available
        if not self.checkSupport():
            sys.exit("NV_path_rendering not supported.")

        # 2. Basic OpenGL settings
        glClearColor(0.0, 0.0, 0.0, 1.0) # Background black
        glEnable(GL_MULTISAMPLE)         # Enable Anti-Aliasing (MSAA)
        
        # 3. Generate paths and load data
        if self.num_paths > 0:
            base_id = glGenPathsNV(self.num_paths)
            self.pathObjs = [base_id + i for i in range(self.num_paths)]

            print("Generated Path IDs:", self.pathObjs)
        
            for path_id, element in zip(self.pathObjs, self.svg_converted_elements):
                svg_path_string_bytes = element['svg_path_string']
                glPathStringNV(path_id, GL_PATH_FORMAT_SVG_NV, len(svg_path_string_bytes), svg_path_string_bytes)

                glPathParameterfNV(path_id, GL_PATH_STROKE_WIDTH_NV, element['stroke_width'])
                glPathParameteriNV(path_id, GL_PATH_JOIN_STYLE_NV, GL_ROUND_NV)
                glPathParameteriNV(path_id, GL_PATH_END_CAPS_NV, GL_ROUND_NV)


    def checkSupport(self):
        try:
            num_extensions = glGetIntegerv(GL_NUM_EXTENSIONS)
            for i in range(num_extensions):
                ext_name = glGetStringi(GL_EXTENSIONS, i)
                if ext_name == b"GL_NV_path_rendering":
                    print("GL_NV_path_rendering is supported.")
                    return True
            print("ERROR: GL_NV_path_rendering missing.")
            return False
        except Exception as e:
            print(f"OpenGL Init Error: {e}")
            return False

    def resizeGL(self, w, h):
        """
        Called when the window size changes (and once at startup).
        This is the correct place to handle the PROJECTION matrix.
        """
        # 1. Set viewport
        glViewport(0, 0, w, h)
        
        # 2. Setup Projection Matrix
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        
        fx = self.projector_intrinsics[0, 0]
        fy = self.projector_intrinsics[1, 1]
        cx = self.projector_intrinsics[0, 2]
        cy = self.projector_intrinsics[1, 2]
        
        z_near = 0.1
        z_far = 10000.0
        
        # Left (x=0 in Image) -> negative X in OpenGL
        l = -cx * z_near / fx
        
        # Right (x=width in Image) -> positive X in OpenGL
        r = (w - cx) * z_near / fx
        
        # Bottom (y=height in Image) -> negative Y in OpenGL
        b = -(h - cy) * z_near / fy
        
        # Top (y=0 in Image) -> positive Y in OpenGL
        t = cy * z_near / fy
        
        glFrustum(l, r, b, t, z_near, z_far)

        # print("Current Matrix Mode: ", glGetIntegerv(GL_MATRIX_MODE))
        
        glMatrixMode(GL_MODELVIEW)
    
    @pyqtSlot(np.ndarray, np.ndarray)
    def updateTagPose(self, R_ct, tvec):
        """ 
        Update the current tag pose and trigger a redraw.

        Args:
            R_ct (np.ndarray): 3x3 rotation matrix of the tag w.r.t. the camera.
            tvec (np.ndarray): 3x1 translation vector of the tag w.r.t. the camera.
        """
        new_pose = buildExtrinsicMatrix(R_ct, tvec)
        self.current_tag_pose = new_pose
        self.update() # Triggers paintGL
    
    def paintGL(self):
        """
   
        """
        # glDisable(GL_CULL_FACE)
        glClearStencil(0)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glStencilMask(~0)
        glClear(GL_COLOR_BUFFER_BIT | GL_STENCIL_BUFFER_BIT)

        # print("Current Matrix Mode: ", glGetIntegerv(GL_MATRIX_MODE))
        
        # We are already in GL_MODELVIEW mode (thanks to resizeGL)
        glLoadIdentity()
        
        glScale(1.0, -1.0, -1.0)
            
        glMultMatrixf(self.T_proj_cam.T)

        glMultMatrixf(self.current_tag_pose.T)

        glMultMatrixf(self.M_svg_to_tag.T)

        # --- RENDERING LOOP ---
        for pathObj, element in zip(self.pathObjs, self.svg_converted_elements):     
            if element['is_filled']:
                glStencilFillPathNV(pathObj, GL_COUNT_UP_NV, 0x1F)
                
                glEnable(GL_STENCIL_TEST)

                
                glStencilFunc(GL_NOTEQUAL, 0, 0x1F)
                glStencilOp(GL_KEEP, GL_KEEP, GL_ZERO)
                
                glColor3f(*element['fill_color'])
                glCoverFillPathNV(pathObj, GL_BOUNDING_BOX_NV)

                glDisable(GL_STENCIL_TEST)

            if element['stroke_color'] is not None:
                glStencilStrokePathNV(pathObj, 0x1, ~0)

                glEnable(GL_STENCIL_TEST)

                glColor3f(*element['stroke_color'])
                glStencilFunc(GL_EQUAL, 0x1, 0x1)
                glStencilOp(GL_KEEP, GL_KEEP, GL_ZERO)
                
                glCoverStrokePathNV(pathObj, GL_CONVEX_HULL_NV)

                glDisable(GL_STENCIL_TEST)
    
    def computeSVGToTagMatrixAnalytic(self, cam_intrinsics, initial_tag_pose):
        """
        Calculates the SVG to Tag transformation matrix analytically.

        Args:
            cam_intrinsics (np.ndarray): 3x3 camera intrinsic matrix.
            initial_tag_pose (np.ndarray): 4x4 transformation matrix of the tag at time t0.
        Returns:
            np.ndarray: 4x4 transformation matrix from SVG to Tag plane.
        """
        r1 = initial_tag_pose[0:3, 0] # First column of rotation
        r2 = initial_tag_pose[0:3, 1] # Second column of rotation
        t  = initial_tag_pose[0:3, 3] # Translation vector
        
        # Order them in a 3x3 matrix
        M_ext_reduced = np.column_stack((r1, r2, t)) 
        
        H_forward = cam_intrinsics @ M_ext_reduced
        
        # 3. Invert the homography to get from image to tag plane
        # Now map pixels (u,v) back to the tag plane (x,y).
        try:
            H_inv = np.linalg.inv(H_forward)
        except np.linalg.LinAlgError:
            print("Error: Homography matrix is singular!")
            return np.identity(4)
        
        M_baking = np.eye(4, dtype=np.float32)
        
        # Rotation / Scaling part (top-left 2x2 submatrix)
        M_baking[0, 0] = H_inv[0, 0]
        M_baking[0, 1] = H_inv[0, 1]
        M_baking[1, 0] = H_inv[1, 0]
        M_baking[1, 1] = H_inv[1, 1]
        
        # Translation part (last column)
        M_baking[0, 3] = H_inv[0, 2]
        M_baking[1, 3] = H_inv[1, 2]
        
        # Homogeneous coordinate row
        M_baking[3, 0] = H_inv[2, 0]
        M_baking[3, 1] = H_inv[2, 1]
        M_baking[3, 3] = H_inv[2, 2]
        
        print("Calculated Baking Matrix:\n", M_baking)
        
        return M_baking
    
class ProjectorWindow(QMainWindow):
    def __init__(self, gl_widget):
        super().__init__()
        self.setWindowTitle("Projector Output")
        self.setCentralWidget(gl_widget)
        self.resize(1280, 720)

class ControlWindow(QMainWindow):
    def __init__(self, webcam_thread, projector_window):
        super().__init__()
        self.setWindowTitle("Control Panel")
        self.resize(1280, 720)
        self.projector_window = projector_window # Referenz speichern zum Schließen

        # Layout
        central = QWidget()
        layout = QVBoxLayout()
        central.setLayout(layout)
        self.setCentralWidget(central)

        # Kamera Label
        self.camera_label = QLabel("Kamera startet...")
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setStyleSheet("background-color: black;")
        layout.addWidget(self.camera_label)

        # Thread Setup
        self.webcam_thread = webcam_thread
        
        # Verbindung: Thread Bild -> GUI Label
        self.webcam_thread.image_update_signal.connect(self.update_image)
        
        self.webcam_thread.start()

    @pyqtSlot(QImage)
    def update_image(self, image):
        # Bild anzeigen
        pixmap = QPixmap.fromImage(image)
        # Skalieren auf Fenstergröße
        scaled = pixmap.scaled(self.camera_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.camera_label.setPixmap(scaled)

    def closeEvent(self, event):
        # Wenn wir das Kontrollfenster schließen, alles beenden
        self.webcam_thread.stop()
        self.projector_window.close() # Projektor Fenster auch schließen
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    fmt = QSurfaceFormat()
    fmt.setStencilBufferSize(8)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setSamples(8) 
    QSurfaceFormat.setDefaultFormat(fmt)

    svg = "tests/svgs/raw_image_0_step_001_drawn.svg"
    test_elements = convertSVGElementsToBytePaths(svg)

    calibration_data_path = 'data/projector_camera_calibration/calibration.yml'
    cam_K, cam_kc, projector_intrinsics, _, R, T = get_calibration_data(calibration_data_path)

    R_ct = np.array([
        [ 0.93521196, -0.21958008, -0.27778261],
        [ 0.32582255,  0.84079681,  0.43231977],
        [ 0.13862992, -0.49481846,  0.85786738]
    ])

    tvec_ref = np.array([
        [-0.01003388],
        [-0.02722046],
        [ 1.22538255]
    ])

    initial_tag_pose = buildExtrinsicMatrix(R_ct, tvec_ref)
    T_proj_cam = buildExtrinsicMatrix(R, T)

    gl_widget = PathRenderingWidget(test_elements, projector_intrinsics, T_proj_cam, initial_tag_pose, cam_K)

    apriltag_detector = AprilTagDetector(camera_intrinsics=cam_K)

    webcam_thread = WebcamThread(apriltag_detector=apriltag_detector, camera_intrinsics=cam_K, dist_coeffs=cam_kc)
    
    projector_win = ProjectorWindow(gl_widget)
    control_win = ControlWindow(webcam_thread, projector_win)
    webcam_thread.pose_update_signal.connect(gl_widget.updateTagPose)

    projector_win.show()
    control_win.show()
    
    sys.exit(app.exec())