import sys
import os
from PyQt6.QtWidgets import QApplication
from app.ui.main_window import MainWindow

# Disable High DPI scaling if necessary (matches your legacy code)
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = MainWindow()
    # window.show() # MainWindow handles showing itself via setupScreens()
    
    sys.exit(app.exec())