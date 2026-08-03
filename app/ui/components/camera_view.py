from PyQt6.QtWidgets import QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QPixmap, QImage

class CameraView(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: black; border: 2px solid #4c566a;")
        self.setMinimumSize(1280, 720)
        self.scaled_pixmap = None

    @pyqtSlot(QImage)
    def setImage(self, image: QImage):
        """Slot to receive the QImage from the worker."""
        if image.isNull():
            return
            
        # Convert to Pixmap
        pixmap = QPixmap.fromImage(image)
        
        # Scale to fit the label while keeping aspect ratio
        # Qt.TransformationMode.SmoothTransformation is better quality but slower. 
        # FastTransformation is good for high FPS live feed.
        self.scaled_pixmap = pixmap.scaled(
            self.size(), 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.FastTransformation
        )
        
        self.setPixmap(self.scaled_pixmap)

    def resizeEvent(self, event):
        """Handle resize to ensure image scales correctly."""
        if self.pixmap() and not self.pixmap().isNull():
            # If we have an image, re-scale it to the new size
            # (In a real app, you might cache the original pixmap to avoid quality loss on repeated resize)
            pass
        super().resizeEvent(event)