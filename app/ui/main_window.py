import sys
from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QApplication
from PyQt6.QtGui import QScreen
from screeninfo import get_monitors

from app.core.config import Config
from app.vision.worker import VisionWorker
from app.rendering.projector_window import ProjectorWindow
from app.ui.pages.start_page import StartPage
from app.ui.components.screen_selector import ScreenSelectorDialog

# Pages
from app.ui.pages.creation_page import CreationPage

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

        # 2. Setup Vision Worker (Global Thread)
        self.vision_worker = VisionWorker()
        
        # 3. Setup Projector Window
        self.projector_window = ProjectorWindow()
        
        # 4. Setup Screens (Dialog)
        if not self.setupScreens():
            # If dialog was cancelled, we exit
            sys.exit(0)
        
        # 5. Connect Vision -> Projector
        self.vision_worker.pose_update_signal.connect(self.projector_window.gl_widget.updateTagPose)
        self.vision_worker.baking_update_signal.connect(self.projector_window.gl_widget.setBakingMatrix)
        
        # 6. GUI Stack Setup
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        self.initPages()

    def initPages(self):
        """Initializes and adds all pages to the stack."""
        
        # Page 0: Start Page
        self.start_page = StartPage()
        self.start_page.create_manual_clicked.connect(self.gotoCreationPage)
        self.start_page.load_manual_clicked.connect(self.gotoLoadPage)
        self.start_page.quit_clicked.connect(self.close)
        
        self.stack.addWidget(self.start_page)
        
        # Page 1: Creation Page
        self.creation_page = CreationPage(self.vision_worker)
        self.creation_page.quit_clicked.connect(self.gotoStartPage)
        # Capture logic will follow later
        
        self.stack.addWidget(self.creation_page)

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
            
            # 1. Place GUI Window
            # Move to the top-left of the selected screen with a small offset
            self.move(gui_screen.geometry().x() + 50, gui_screen.geometry().y() + 50)
            self.resize(3840, 2160)
            self.show()
            
            # 2. Place Projector Window
            # Move to the selected screen but slightly offset so they don't perfectly overlap
            self.projector_window.move(proj_screen.geometry().x() + 100, proj_screen.geometry().y() + 100)
            self.projector_window.resize(1280, 720)
            self.projector_window.show()
            
        else:
            print("Starting in PRODUCTION MODE (Fullscreen)")
            
            # 1. Place GUI Window
            self.setGeometry(gui_screen.geometry())
            self.showFullScreen()
            
            # 2. Place Projector Window
            self.projector_window.setGeometry(proj_screen.geometry())
            self.projector_window.showFullScreen()
            
        return True

    def gotoCreationPage(self):
        self.stack.setCurrentWidget(self.creation_page)
        
    def gotoStartPage(self):
        self.stack.setCurrentWidget(self.start_page)

    def gotoLoadPage(self):
        print("Navigating to Load Page... (To be implemented)")

    def closeEvent(self, event):
        self.vision_worker.stop()
        self.projector_window.close()
        event.accept()