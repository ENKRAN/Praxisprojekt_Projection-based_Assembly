from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

class StartPage(QWidget):
    # Signals to communicate with MainWindow
    create_manual_clicked = pyqtSignal()
    load_manual_clicked = pyqtSignal()
    quit_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        label = QLabel("Projection-Based Augmented Reality\nAssembly Working Station")
        label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        label.setStyleSheet("color: white;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        # Buttons
        btn_style = """
            QPushButton {
                background-color: #414a5c; 
                color: white; 
                border: 2px solid #d8dee9;
                border-radius: 15px;
                padding: 10px;
            }
            QPushButton:pressed {
                background-color: #3b4252;
            }
        """

        btn_create = QPushButton("Create Manual")
        btn_create.setFont(QFont("Arial", 20))
        btn_create.setFixedSize(300, 100)
        btn_create.setStyleSheet(btn_style)
        btn_create.clicked.connect(self.create_manual_clicked.emit)

        btn_load = QPushButton("Load Manual")
        btn_load.setFont(QFont("Arial", 20))
        btn_load.setFixedSize(300, 100)
        btn_load.setStyleSheet(btn_style)
        btn_load.clicked.connect(self.load_manual_clicked.emit)

        btn_quit = QPushButton("Quit")
        btn_quit.setFont(QFont("Arial", 20))
        btn_quit.setFixedSize(300, 100)
        btn_quit.setStyleSheet(btn_style)
        btn_quit.clicked.connect(self.quit_clicked.emit)

        layout.addWidget(btn_create, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(btn_load, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(btn_quit, alignment=Qt.AlignmentFlag.AlignCenter)