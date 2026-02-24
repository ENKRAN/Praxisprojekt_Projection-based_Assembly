from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

class LoadPage(QWidget):
    back_clicked = pyqtSignal()
    manual_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(30)

        # Header
        title = QLabel("Select a Published Manual")
        title.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # List Widget for Touch
        self.manual_list = QListWidget()
        self.manual_list.setStyleSheet("""
            QListWidget {
                background-color: #3b4252;
                border: 2px solid #4c566a;
                border-radius: 15px;
                color: #eceff4;
                font-size: 28px;
                padding: 10px;
            }
            QListWidget::item {
                padding: 20px;
                border-bottom: 1px solid #4c566a;
            }
            QListWidget::item:selected {
                background-color: #5e81ac;
                color: white;
                border-radius: 10px;
            }
        """)
        layout.addWidget(self.manual_list)

        # Buttons
        button_layout = QHBoxLayout()
        
        self.btn_back = QPushButton("Back to Start")
        self.btn_load = QPushButton("Start Assembly")
        self.btn_load.setEnabled(False)
        
        for btn in [self.btn_back, self.btn_load]:
            btn.setMinimumHeight(80)
            btn.setFont(QFont("Arial", 24, QFont.Weight.Bold))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #434c5e; color: white; border-radius: 15px;
                }
                QPushButton:pressed { background-color: #2e3440; }
                QPushButton:disabled { background-color: #3b4252; color: #4c566a; }
            """)

        self.btn_load.setStyleSheet(self.btn_load.styleSheet().replace("#434c5e", "#a3be8c"))

        button_layout.addWidget(self.btn_back)
        button_layout.addWidget(self.btn_load)
        layout.addLayout(button_layout)

        # Connections
        self.btn_back.clicked.connect(self.back_clicked.emit)
        self.btn_load.clicked.connect(self.onLoadClicked)
        self.manual_list.itemSelectionChanged.connect(self.onSelectionChanged)

    def populateList(self, manuals: list):
        """
        Fills the list widget with available manuals. Expects a list of (id, title) tuples.

        Args:
            manuals (list): List of tuples, where each tuple is (manual_id, manual_title).     
        """
        self.manual_list.clear()
        self.btn_load.setEnabled(False)
        
        for manual_id, manual_title in manuals:
            item = QListWidgetItem(manual_title)
            # We hide the manual_id in the item data for later retrieval when an item is selected
            item.setData(Qt.ItemDataRole.UserRole, manual_id)
            self.manual_list.addItem(item)

    def onSelectionChanged(self):
        # Button activation based on selection
        self.btn_load.setEnabled(bool(self.manual_list.selectedItems()))

    def onLoadClicked(self):
        selected_items = self.manual_list.selectedItems()
        if selected_items:
            manual_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.manual_selected.emit(manual_id)