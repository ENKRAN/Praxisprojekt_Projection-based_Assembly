from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

class RemotePage(QWidget):
    """
    The UI page for Remote Assistance mode. 
    Displays the live camera feed and connection status.
    """
    quit_clicked = pyqtSignal()
    snapshot_clicked = pyqtSignal()

    def __init__(self, camera_view):
        super().__init__()
        self.camera_view = camera_view
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- HEADER (Status Info) ---
        self.status_label = QLabel("Waiting for Remote Expert...")
        self.status_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        self.status_label.setStyleSheet("color: #ebcb8b; background-color: #3b4252; padding: 20px; border-radius: 15px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label, stretch=0)

        # --- CONTENT AREA (Camera only) ---
        content_layout = QHBoxLayout()
        self.camera_view.setFixedSize(1280, 720) 
        
        cam_container = QVBoxLayout()
        cam_container.addWidget(self.camera_view, alignment=Qt.AlignmentFlag.AlignCenter)
        content_layout.addLayout(cam_container, stretch=1)
        
        main_layout.addLayout(content_layout, stretch=1)

        # --- BOTTOM CONTROLS ---
        controls_layout = QHBoxLayout()
        
        # Snapshot Button
        self.btn_snapshot = QPushButton("📸 Bake Tag (Take Snapshot)")
        self.btn_snapshot.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.btn_snapshot.setMinimumHeight(60)
        self.btn_snapshot.setStyleSheet("""
            QPushButton { 
                background-color: #5e81ac; 
                color: white; 
                border-radius: 10px; 
            } 
            QPushButton:pressed { background-color: #4c6a8d; }
        """)
        self.btn_snapshot.clicked.connect(self.snapshot_clicked.emit)
        
        # Quit Button
        self.btn_quit = QPushButton("Quit Remote Mode")
        self.btn_quit.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.btn_quit.setMinimumHeight(60)
        self.btn_quit.setStyleSheet("""
            QPushButton { 
                background-color: #bf616a; 
                color: white; 
                border-radius: 10px; 
            } 
            QPushButton:pressed { background-color: #8f4b52; }
        """)
        self.btn_quit.clicked.connect(self.quit_clicked.emit)
        
        controls_layout.addWidget(self.btn_snapshot)
        controls_layout.addWidget(self.btn_quit)
        
        main_layout.addLayout(controls_layout, stretch=0)

    def setConnectionStatus(self, is_connected: bool):
        """Updates the header based on the connection status."""
        if is_connected:
            self.status_label.setText("Remote Expert Connected - Laser Pointer Active")
            self.status_label.setStyleSheet("color: #a3be8c; background-color: #3b4252; padding: 20px; border-radius: 15px;")
        else:
            self.status_label.setText("Waiting for Remote Expert...")
            self.status_label.setStyleSheet("color: #ebcb8b; background-color: #3b4252; padding: 20px; border-radius: 15px;")