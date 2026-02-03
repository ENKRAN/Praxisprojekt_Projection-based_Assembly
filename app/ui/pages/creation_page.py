from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QMessageBox

from app.ui.components.camera_view import CameraView

class CreationPage(QWidget):
    # Signals for navigation/actions
    capture_clicked = pyqtSignal()
    save_step_clicked = pyqtSignal()
    undo_step_clicked = pyqtSignal()
    save_manual_clicked = pyqtSignal()
    quit_clicked = pyqtSignal()

    def __init__(self, vision_worker, parent=None):
        super().__init__(parent)
        self.vision_worker = vision_worker
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
        
        self.camera_view = CameraView()
        self.camera_view.setFixedSize(1280, 720) 
        
        video_container.addWidget(self.camera_view)
        video_container.addStretch()
        
        layout.addLayout(video_container)

        # --- 3. Bottom: Buttons ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        btn_style = """
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
            btn.setStyleSheet(btn_style)
            btn.setMinimumHeight(60)
            button_layout.addWidget(btn)

        layout.addLayout(button_layout)

        self.setButtonsState(running=False)

    def setupConnections(self):
        self.vision_worker.image_update_signal.connect(self.camera_view.setImage)
        self.vision_worker.status_signal.connect(self.updateStatus)
        
        # Connect the critical error signal
        self.vision_worker.error_signal.connect(self.onCameraError)

        # Button Actions
        self.btn_start.clicked.connect(self.onStartLive)
        self.btn_stop.clicked.connect(self.onStopLive)
        self.btn_capture.clicked.connect(self.onCapture)
        self.btn_save_step.clicked.connect(self.save_step_clicked.emit)
        self.btn_undo.clicked.connect(self.undo_step_clicked.emit)
        self.btn_save_manual.clicked.connect(self.save_manual_clicked.emit)
        self.btn_quit.clicked.connect(self.onQuit)

    def onStartLive(self):
        if not self.vision_worker.isRunning():
            self.status_label.setText("Status: Starting Camera...")
            self.vision_worker.start()
            self.status_label.setText("Status: Camera Running")
        else:
            self.status_label.setText("Status: Camera already running")

    def onStopLive(self):
        if self.vision_worker.isRunning():
            self.status_label.setText("Status: Stopping Camera...")
            self.vision_worker.stop()
            self.status_label.setText("Status: Live Feed Stopped")
            self.camera_view.clear()
            self.setButtonsState(running=False)
        else:
            self.status_label.setText("Status: Camera is not running")

    def onCapture(self):
        if self.vision_worker.isRunning():
            self.status_label.setText("Status: Capturing Photo...")
            self.vision_worker.triggerSnapshot()
            self.capture_clicked.emit()
        else:
             self.status_label.setText("Status: Cannot capture - Camera not running")

    def onQuit(self):
        """Stops the camera before leaving the page."""
        self.onStopLive()
        self.quit_clicked.emit()

    def onCameraError(self, error_message: str):
        """Displays popup on critical failure and resets UI."""
        self.status_label.setText("Status: Camera Error")
        QMessageBox.critical(self, "Camera Error", f"Critical Camera Failure:\n\n{error_message}\n\nPlease check connection and restart.")
        
        # Force UI reset
        self.onStopLive()
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