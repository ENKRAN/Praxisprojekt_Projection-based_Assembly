from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QComboBox, 
                             QPushButton, QApplication, QMessageBox, QCheckBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QScreen

# Import our new Settings Manager
from app.core.user_settings import UserSettings

class ScreenSelectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Monitor Setup")
        self.setModal(True)
        self.resize(450, 350)
        
        self.selected_gui_screen = None
        self.selected_proj_screen = None
        self.is_debug = False
        
        # 1. Load previous settings
        self.settings = UserSettings.load()
        saved_gui_name = self.settings.get("gui_screen_name", "")
        saved_proj_name = self.settings.get("proj_screen_name", "")
        saved_debug = self.settings.get("debug_mode", False)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        info = QLabel("Select displays for the application.\nSettings are saved automatically.")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Detect Screens
        self.screens = QApplication.screens()
        # Create user-friendly names list
        screen_items = [f"{i}: {s.name()} ({s.size().width()}x{s.size().height()})" for i, s in enumerate(self.screens)]
        
        # --- GUI Dropdown ---
        layout.addWidget(QLabel("GUI / Touchscreen:"))
        self.combo_gui = QComboBox()
        self.combo_gui.addItems(screen_items)
        layout.addWidget(self.combo_gui)
        
        # --- Projector Dropdown ---
        layout.addWidget(QLabel("Projector:"))
        self.combo_proj = QComboBox()
        self.combo_proj.addItems(screen_items)
        layout.addWidget(self.combo_proj)
        
        # --- Restore Selection Logic ---
        # Attempt to find the saved monitors
        gui_index_found = self.find_screen_index(saved_gui_name)
        proj_index_found = self.find_screen_index(saved_proj_name)
        
        # If found -> set. Otherwise defaults (0 and 1)
        if gui_index_found >= 0:
            self.combo_gui.setCurrentIndex(gui_index_found)
        else:
            self.combo_gui.setCurrentIndex(0)
            
        if proj_index_found >= 0:
            self.combo_proj.setCurrentIndex(proj_index_found)
        elif len(self.screens) > 1:
            self.combo_proj.setCurrentIndex(1)
        
        # --- Debug Checkbox ---
        self.check_debug = QCheckBox("Debug Mode (Windowed, allow overlap)")
        self.check_debug.setChecked(saved_debug)
        layout.addWidget(self.check_debug)
        
        # OK Button
        btn_ok = QPushButton("Launch Application")
        btn_ok.setMinimumHeight(40)
        btn_ok.clicked.connect(self.on_apply)
        layout.addWidget(btn_ok)
        
    def find_screen_index(self, screen_name):
        """Helper to find the index of a screen by its name."""
        if not screen_name: 
            return -1
        for i, s in enumerate(self.screens):
            if s.name() == screen_name:
                return i
        return -1
        
    def on_apply(self):
        gui_idx = self.combo_gui.currentIndex()
        proj_idx = self.combo_proj.currentIndex()
        self.is_debug = self.check_debug.isChecked()
        
        # Verification
        if not self.is_debug and gui_idx == proj_idx:
            QMessageBox.warning(self, "Conflict", 
                                "GUI and Projector cannot be on the same screen in Production Mode!\n"
                                "Please select different screens or enable 'Debug Mode'.")
            return
            
        self.selected_gui_screen = self.screens[gui_idx]
        self.selected_proj_screen = self.screens[proj_idx]
        
        # --- SAVE SETTINGS ---
        new_settings = {
            "gui_screen_name": self.selected_gui_screen.name(),
            "proj_screen_name": self.selected_proj_screen.name(),
            "debug_mode": self.is_debug
        }
        UserSettings.save(new_settings)
        
        self.accept()
        
    @staticmethod
    def get_screens(parent=None):
        dialog = ScreenSelectorDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_gui_screen, dialog.selected_proj_screen, dialog.is_debug
        return None, None, False