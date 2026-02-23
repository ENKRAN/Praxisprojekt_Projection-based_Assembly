from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QMessageBox

class CreationPage(QWidget):
    # Signals for navigation/actions
    start_live_clicked = pyqtSignal()
    stop_live_clicked = pyqtSignal()
    capture_clicked = pyqtSignal()
    save_step_clicked = pyqtSignal()
    undo_step_clicked = pyqtSignal()
    save_manual_clicked = pyqtSignal()
    quit_clicked = pyqtSignal()

    def __init__(self, camera_view, parent=None):
        super().__init__(parent)
        self.camera_view = camera_view
        self.initUI()
        self.setupConnections()

    def initUI(self):
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # --- 1. Top: Status Bar ---
        self.status_label = QLabel("Status: Ready")
        self.status_label.setFixedHeight(50)
        self.status_label.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
        self.status_label.setFont(QFont("Arial", 16))
        self.status_label.setStyleSheet("color: white; background-color: #2e3440; padding: 5px;")
        layout.addWidget(self.status_label)

        # --- 2. Center: Live Camera Feed ---
        video_container = QHBoxLayout()
        video_container.addStretch()
        
        self.camera_view.setFixedSize(1280, 720) 
        
        video_container.addWidget(self.camera_view)
        video_container.addStretch()
        
        layout.addLayout(video_container)

        # --- 3. Bottom: Buttons ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        btn_style_default = """
            QPushButton {
                background-color: #414a5c; 
                color: white; 
                border: 2px solid #d8dee9;
                border-radius: 10px;
                padding: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #3b4252;
            }
            QPushButton:disabled {
                background-color: #2e3440;  /* Very dark grey/blue */
                color: #606672;             /* Dim grey text */
                border: 2px solid #3b4252;  /* Dark border */
            }
        """

        self.btn_start = QPushButton("Start Live Feed")
        self.btn_stop = QPushButton("Stop Live Feed")
        self.btn_capture = QPushButton("Capture Photo")
        self.btn_save_step = QPushButton("Save Step")
        self.btn_undo = QPushButton("Undo Step")
        self.btn_save_manual = QPushButton("Save Manual")
        self.btn_quit = QPushButton("Quit")

        for btn in [self.btn_start, self.btn_stop, self.btn_capture, self.btn_save_step, self.btn_undo, self.btn_save_manual, self.btn_quit]:
            btn.setStyleSheet(btn_style_default)
            btn.setMinimumHeight(60)
            button_layout.addWidget(btn)

        self.btn_save_step.setVisible(False) 
        self.btn_undo.setVisible(False)

        layout.addLayout(button_layout)

        self.setInitialButtonsState(enabled=True)

    def setupConnections(self):
        # Button Actions
        self.btn_start.clicked.connect(self.start_live_clicked.emit)
        self.btn_stop.clicked.connect(self.stop_live_clicked.emit)
        self.btn_capture.clicked.connect(self.capture_clicked.emit)
        self.btn_save_step.clicked.connect(self.save_step_clicked.emit)
        self.btn_undo.clicked.connect(self.undo_step_clicked.emit)
        self.btn_save_manual.clicked.connect(self.save_manual_clicked.emit)
        self.btn_quit.clicked.connect(self.onQuit)
        
    def onQuit(self):
        """Stops the camera before leaving the page."""
        self.stop_live_clicked.emit()
        self.quit_clicked.emit()

    def onCameraError(self, error_message: str):
        """Displays popup on critical failure and resets UI."""
        self.status_label.setText("Status: Camera Error")
        QMessageBox.critical(self, "Camera Error", f"Critical Camera Failure:\n\n{error_message}\n\nPlease check connection and restart.")
        
        # Force UI reset
        self.stop_live_clicked.emit()
        self.setButtonsState(running=False)

    def updateStatus(self, message: str):
        """Updates status label and toggles buttons based on state."""
        self.status_label.setText(message)
        
        # Check if the message implies a stable running state
        if "Running" in message:
            self.setButtonsState(running=True)
            self.btn_capture.setEnabled(True)
        elif "Connecting" in message or "Retrying" in message:
            # We are in a transition state
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)    # Allow user to abort
            self.btn_capture.setEnabled(False) # Prevent capture during reconnect

    def setButtonsState(self, running: bool):
        """Helper to set button states."""
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_capture.setEnabled(running)
        self.btn_save_step.setEnabled(running)
        self.btn_undo.setEnabled(running)
        self.btn_save_manual.setEnabled(running)

    def setInitialButtonsState(self, enabled: bool):
        """Initial state for buttons when page loads."""
        self.btn_start.setEnabled(enabled)
        self.btn_stop.setEnabled(not enabled)
        self.btn_capture.setEnabled(not enabled)
        self.btn_save_step.setEnabled(not enabled)
        self.btn_undo.setEnabled(not enabled)
        self.btn_save_manual.setEnabled(not enabled)
        self.btn_quit.setEnabled(enabled)

    def showReviewUI(self, is_review_mode: bool):
        """
        Toggles UI between Live Feed mode and Review mode after capturing a photo.
         - In Review Mode: Show Confirm/Discard buttons, hide camera controls.
         - In Live Mode: Show camera controls, hide review buttons.
         - Update status label accordingly.
         - Style buttons to visually differentiate actions.

        Args:
            is_review_mode (bool): True to show review UI, False to show live feed UI
        """
        if is_review_mode:
            # === REVIEW MODE (after drawing) ===
            self.status_label.setText("Review: Check Projection on Object")
            
            # Hide Camera buttons, so user focuses on review actions
            self.btn_start.setVisible(False)
            self.btn_stop.setVisible(False)
            self.btn_capture.setVisible(False)
            
            # Button 1: Confirm & Save (Grün)
            self.btn_save_step.setVisible(True)
            self.btn_save_step.setEnabled(True)
            self.btn_save_step.setText("Confirm & Save") 
            self.btn_save_step.setStyleSheet("background-color: #a3be8c; color: white; font-weight: bold; font-size: 16px; padding: 10px; border-radius: 10px;")
            
            # Button 2: Discard & Edit (Rot)
            self.btn_undo.setVisible(True)
            self.btn_undo.setEnabled(True)
            self.btn_undo.setText("Discard / Edit")
            self.btn_undo.setStyleSheet("background-color: #bf616a; color: white; font-weight: bold; font-size: 16px; padding: 10px; border-radius: 10px;")

        else:
            # === LIVE MODE (camera running) ===
            self.status_label.setText("Status: Live Feed Ready")
            
            self.btn_start.setVisible(True)
            self.btn_stop.setVisible(True)
            self.btn_capture.setVisible(True)
            
            self.btn_save_step.setVisible(False)
            self.btn_undo.setVisible(False)
            
            # Reset button styles to default for live mode
            self.btn_save_step.setText("Save Step")
            self.btn_undo.setText("Undo Step")