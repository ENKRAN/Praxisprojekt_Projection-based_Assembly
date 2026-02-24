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
        main_layout = QVBoxLayout(self)

        # Title
        top_layout = QVBoxLayout()
        top_layout.addStretch()
        label = QLabel("Projection-Based Augmented Reality\nAssembly Working Station")
        label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        label.setStyleSheet("color: white;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(label)
        top_layout.addStretch()

        bottom_layout = QVBoxLayout()
        bottom_layout.setSpacing(20)
        bottom_layout.addStretch()
        btn_create = QPushButton("Create Manual")
        btn_create.setFont(QFont("Arial", 20))
        btn_create.setFixedSize(300, 100)
        btn_create.clicked.connect(self.create_manual_clicked.emit)

        btn_load = QPushButton("Load Manual")
        btn_load.setFont(QFont("Arial", 20))
        btn_load.setFixedSize(300, 100)
        btn_load.clicked.connect(self.load_manual_clicked.emit)

        btn_quit = QPushButton("Quit")
        btn_quit.setFont(QFont("Arial", 20))
        btn_quit.setFixedSize(300, 100)
        btn_quit.clicked.connect(self.quit_clicked.emit)

        bottom_layout.addWidget(btn_create, alignment=Qt.AlignmentFlag.AlignHCenter)
        bottom_layout.addWidget(btn_load, alignment=Qt.AlignmentFlag.AlignHCenter)
        bottom_layout.addWidget(btn_quit, alignment=Qt.AlignmentFlag.AlignHCenter)
        bottom_layout.addStretch()

        main_layout.addLayout(top_layout, stretch=1)
        main_layout.addLayout(bottom_layout, stretch=1)