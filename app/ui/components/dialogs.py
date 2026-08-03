from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QWidget, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

class PopupDialog(QDialog):
    def __init__(self, parent=None, header="", dialog_type="buttons", button_count=0, button_texts=[], placeholder_text=""):
        super().__init__(parent)
        self.user_input = None
        self.dialog_type = dialog_type

        # Frameless Window Setup
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        # Dynamic sizing
        base_height = 200
        if dialog_type == "text_input":
            content_height = base_height + 120
        else:
            button_height = 80
            spacing_per_button = 15
            content_height = base_height + (button_count * button_height) + (button_count * spacing_per_button)
        
        self.resize(500, content_height)

        # Shadow Widget
        self.shadow_widget = QWidget(self)
        self.shadow_widget.setObjectName("shadow_widget")
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(0, 0, 0, 160))
        self.shadow_widget.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.shadow_widget)
        layout.setContentsMargins(30, 30, 30, 30) 
        layout.setSpacing(20)

        # Title
        title = QLabel(header)
        font_title = QFont("Arial", 20, QFont.Weight.Bold)
        title.setFont(font_title)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; border: none;")
        layout.addWidget(title)

        if dialog_type == "text_input":
            self.text_input = QLineEdit()
            self.text_input.setPlaceholderText(placeholder_text)
            self.text_input.setMinimumHeight(60)
            self.text_input.setStyleSheet("""
                QLineEdit {
                    font-size: 18px;
                    padding: 10px;
                    border: 2px solid #4c566a;
                    border-radius: 10px;
                    background-color: #d8dee9;
                    color: #2e3440;
                }
            """)
            layout.addWidget(self.text_input)

            button_layout = QHBoxLayout()
            button_layout.setSpacing(15)
            
            self.createBtn("OK", self.onTextInputOk, button_layout)
            self.createBtn("Cancel", self.reject, button_layout)
            
            layout.addLayout(button_layout)
            self.text_input.setFocus()

        else:
            # Multiple Choice Buttons
            for i in range(button_count):
                text = button_texts[i] if i < len(button_texts) else f"Option {i}"
                btn = QPushButton(text)
                self.styleButton(btn)
                btn.clicked.connect(lambda _, t=text: self.onChoice(t))
                layout.addWidget(btn)

    def resizeEvent(self, event):
        self.shadow_widget.setGeometry(10, 10, self.width() - 20, self.height() - 20)
        super().resizeEvent(event)

    def createBtn(self, text, callback, layout):
        btn = QPushButton(text)
        self.styleButton(btn)
        btn.clicked.connect(callback)
        layout.addWidget(btn)

    def styleButton(self, btn):
        btn.setMinimumHeight(60)
        btn.setFont(QFont("Arial", 18))
        btn.setStyleSheet("""
            QPushButton {
                background-color: #414a5c; 
                color: white; 
                border: 2px solid #d8dee9;
                border-radius: 10px;
            }
            QPushButton:pressed {
                background-color: #3b4252;
            }
        """)

    def onChoice(self, choice_text):
        self.user_input = choice_text
        self.accept()

    def onTextInputOk(self):
        self.user_input = self.text_input.text().strip()
        if self.user_input:
            self.accept()

    def isPopupResultValid(self, result):
        if result == QDialog.DialogCode.Rejected or not self.user_input:
            return False
        return True