import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import pyqtSlot, Qt
from PyQt6.QtGui import QSurfaceFormat, QPixmap, QImage

from OpenGL.GL import *
from OpenGL.GL.NV.path_rendering import *

from legacy_scripts.svg_manipulation import convertSVGElementsToBytePaths
from src.setup import get_calibration_data
from src.setup import buildExtrinsicMatrix
from legacy_scripts.apriltag_detection import AprilTagTrackingWorker

class PathRenderingWidget(QOpenGLWidget):
    def __init__(self, svg_converted_elements, projector_intrinsics, T_proj_cam, tag_size, parent=None):
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

        self.tag_size = tag_size
        self.is_baked = False

        self.current_tag_pose = np.eye(4, dtype=np.float32)
        self.M_svg_to_tag = np.eye(4, dtype=np.float32) 

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
    def setBakingMatrix(self, homography, color_img):
        """
        Receives a homography and computes the baking matrix (ONE TIME).
        """
        print("Computing baking matrix from snapshot homography...")
        self.M_svg_to_tag = self.computeSVGToTagMatrix(homography, self.tag_size)
        self.is_baked = True
        self.update()

    @pyqtSlot(np.ndarray, np.ndarray)
    def updateTagPose(self, R_ct, tvec):
        """
        Updates the current tag pose to be used in paintGL.
        """
        new_pose = buildExtrinsicMatrix(R_ct, tvec)
        self.current_tag_pose = new_pose
        
        if self.is_baked:
            self.update()
    
    def paintGL(self):
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

        if not self.is_baked:
            return

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
    
    def computeSVGToTagMatrix(self, homography, tag_size_meters):
        """
        Calculates the Transformation from Image Pixels to Physical Tag Plane.
        
        Args:
            tag: The pupil_apriltags detection object.
            tag_size_meters (float): The physical size of the tag (e.g. 0.05).
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
    
class ProjectorWindow(QMainWindow):
    def __init__(self, gl_widget, width=1280, height=720):
        super().__init__()
        self.setWindowTitle("Projector Output")
        self.setCentralWidget(gl_widget)
        self.resize(width, height)

class ControlWindow(QMainWindow):
    def __init__(self, apriltag_tracking_thread, projector_window):
        super().__init__()
        self.setWindowTitle("Control Panel")
        self.resize(1280, 720)
        self.projector_window = projector_window # Store reference to close later

        # Layout
        central = QWidget()
        layout = QVBoxLayout()
        central.setLayout(layout)
        self.setCentralWidget(central)

        # Camera label
        self.camera_label = QLabel("Camera starting...")
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setStyleSheet("background-color: black;")
        layout.addWidget(self.camera_label)

        self.btn_snapshot = QPushButton("Set Reference Frame (Bake SVG)")
        self.btn_snapshot.setMinimumHeight(50)
        self.btn_snapshot.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.btn_snapshot.clicked.connect(self.onSnapshotClicked)
        layout.addWidget(self.btn_snapshot)

        # Thread setup
        self.apriltag_tracking_thread = apriltag_tracking_thread
        self.apriltag_tracking_thread.image_update_signal.connect(self.updateImage)
        self.apriltag_tracking_thread.start()

    def onSnapshotClicked(self):
        # Ruft die Methode im Thread auf, die das Flag setzt
        self.apriltag_tracking_thread.triggerSnapshot()
        self.btn_snapshot.setText("Snapshot Requested... (Hold Steady!)")

    @pyqtSlot(QImage)
    def updateImage(self, image):
        # Display image
        pixmap = QPixmap.fromImage(image)
        # Scale to window size
        scaled = pixmap.scaled(self.camera_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.camera_label.setPixmap(scaled)

    def closeEvent(self, event):
        # When we close the control window, shut everything down
        self.apriltag_tracking_thread.stop()
        self.projector_window.close()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    fmt = QSurfaceFormat()
    fmt.setStencilBufferSize(8)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setSamples(8) 
    QSurfaceFormat.setDefaultFormat(fmt)

    svg = "tests/result/baking_snapshot_drawn.svg"
    test_elements = convertSVGElementsToBytePaths(svg)

    calibration_data_path = 'data/projector_camera_calibration/calibration.yml'
    cam_K, cam_kc, projector_intrinsics, _, R, T = get_calibration_data(calibration_data_path)

    T_proj_cam = buildExtrinsicMatrix(R, T)

    TAG_SIZE = 0.038

    gl_widget = PathRenderingWidget(test_elements, projector_intrinsics, T_proj_cam, TAG_SIZE)
    apriltag_tracking_thread = AprilTagTrackingWorker(width=1280, height=720, cam_intrinsics=cam_K, cam_dist_coeffs=cam_kc)
    
    projector_win = ProjectorWindow(gl_widget, width=1280, height=720)
    control_win = ControlWindow(apriltag_tracking_thread, projector_win)
    apriltag_tracking_thread.pose_update_signal.connect(gl_widget.updateTagPose)
    apriltag_tracking_thread.baking_update_signal.connect(gl_widget.setBakingMatrix)
    projector_win.showFullScreen()
    control_win.show()
    
    sys.exit(app.exec())