import sys
from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox, QDialog

# Core / Configuration
from app.core.config import Config
from app.core.flowchart_manager import FlowchartManager
from app.core.manual_manager import ManualManager

# Vision / Hardware
from app.vision.worker import VisionWorker
from app.rendering.projector_window import ProjectorWindow

# UI Components & Pages
from app.ui.components.screen_selector import ScreenSelectorDialog
from app.ui.components.dialogs import PopupDialog
from app.ui.pages.start_page import StartPage
from app.ui.pages.creation_page import CreationPage
from app.ui.pages.node_selection_page import NodeSelectionPage

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AR Assembly System - Control")
        
        # 1. Load Configuration
        try:
            Config.loadCalibration("data/projector_camera_calibration/calibration.yml")
        except Exception as e:
            print(f"Error loading calibration: {e}")
            sys.exit(1)

        # 2. Logic Managers
        self.flowchart_manager = FlowchartManager() 
        self.manual_manager = ManualManager()
        
        # Temp Data Storage (RAM) for the current step being created
        self.current_snapshot = None     # The image (NumPy Array)
        self.current_homography = None   # The matrix
        self.current_node_type = None    # The selected node type (e.g., "operation")
        self.current_tag_id = -1         # ID of the tag in the snapshot

        # 3. Setup Hardware & Windows
        self.vision_worker = VisionWorker()
        self.projector_window = ProjectorWindow()
        
        # Screen Setup via Dialog
        if not self.setupScreens():
            sys.exit(0)
        
        # 4. Connect Vision -> Projector
        # VisionWorker now sends (R, t, tag_id) -> ProjectorWindow must accept this
        self.vision_worker.pose_update_signal.connect(self.projector_window.gl_widget.updateTagPose)
        self.vision_worker.baking_update_signal.connect(self.projector_window.gl_widget.setBakingMatrix)
        
        # Connect Vision -> MainWindow (Catch Snapshot)
        self.vision_worker.baking_update_signal.connect(self.onSnapshotTaken)
        
        # 5. GUI Stack Setup
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        self.initPages()

    def initPages(self):
        # Page 0: Start Page
        self.start_page = StartPage()
        # CHANGED: Ask for name first, then start
        self.start_page.create_manual_clicked.connect(self.onRequestCreateManual)
        self.start_page.load_manual_clicked.connect(self.gotoLoadPage)
        self.start_page.quit_clicked.connect(self.close)
        self.stack.addWidget(self.start_page)
        
        # Page 1: Creation Page (Live Camera)
        self.creation_page = CreationPage(self.vision_worker)
        self.creation_page.quit_clicked.connect(self.gotoStartPage)
        self.stack.addWidget(self.creation_page)
        
        # Page 2: Node Selection Page
        self.node_selection_page = NodeSelectionPage()
        self.node_selection_page.node_selected.connect(self.onNodeSelected)
        self.node_selection_page.back_clicked.connect(self.gotoCreationPage)
        self.stack.addWidget(self.node_selection_page)
        
        # Page 3: Drawing Page (Coming in the next step)
        # self.drawing_page = DrawingPage(...)
        # self.stack.addWidget(self.drawing_page)

    def onRequestCreateManual(self):
        """
        NEW: Opens a popup to enter the manual name.
        Then creates the folder structure via ManualManager.
        """
        # We use the existing PopupDialog class
        dialog = PopupDialog(self, 
                             dialog_type="text_input", 
                             header="Create New Manual", 
                             placeholder_text="e.g. Pump_Assembly_V1")
        
        # Execute dialog
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.user_input:
            title = dialog.user_input
            try:
                # Create Manual (Tag ID is initially -1/unknown)
                self.manual_manager.createNewManual(title, tag_id=-1)
                print(f"Manual '{title}' created successfully.")
                
                # Only now switch to the Creation Page (Camera)
                self.gotoCreationPage()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create manual:\n{e}")

    def onSnapshotTaken(self, homography, color_img, tag_id):
        """
        CHANGED: Now also receives the tag_id.
        Called when VisionWorker takes a snapshot.
        """
        print(f"Snapshot received for Tag {tag_id}. Storing data...")
        
        # Store data temporarily
        self.current_homography = homography
        self.current_snapshot = color_img.copy()
        self.current_tag_id = tag_id
        
        # Proceed to selection page
        self.stack.setCurrentWidget(self.node_selection_page)

    def onNodeSelected(self, node_type: str):
        """
        Called when the user selects an icon on the NodeSelectionPage.
        """
        print(f"Node selected: {node_type}")
        self.current_node_type = node_type
        
        # TODO: In the next step, we switch to DrawingPage here
        print("Navigating to Drawing Page (Coming soon)...")
        # self.stack.setCurrentWidget(self.drawing_page)

    def setupScreens(self):
        """
        Identifies screens via Dialog and places windows accordingly.
        Returns True if successful, False if cancelled.
        """
        gui_screen, proj_screen, is_debug = ScreenSelectorDialog.get_screens()
        
        if not gui_screen or not proj_screen:
            return False

        if is_debug:
            print("Starting in DEBUG MODE (Windowed)")
            self.move(gui_screen.geometry().x() + 50, gui_screen.geometry().y() + 50)
            self.resize(3840, 2160)
            self.show()
            
            self.projector_window.move(proj_screen.geometry().x() + 100, proj_screen.geometry().y() + 100)
            self.projector_window.resize(1280, 720)
            self.projector_window.show()
        else:
            print("Starting in PRODUCTION MODE (Fullscreen)")
            self.setGeometry(gui_screen.geometry())
            self.showFullScreen()
            
            self.projector_window.setGeometry(proj_screen.geometry())
            self.projector_window.showFullScreen()
            
        return True

    def gotoCreationPage(self):
        self.stack.setCurrentWidget(self.creation_page)
        
    def gotoStartPage(self):
        self.stack.setCurrentWidget(self.start_page)

    def gotoLoadPage(self):
        print("Load Page not implemented yet.")

    def closeEvent(self, event):
        self.vision_worker.stop()
        self.projector_window.close()
        event.accept()