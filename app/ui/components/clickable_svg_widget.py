from PyQt6.QtWidgets import QWidget
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QPainter
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty

class ClickableSvgWidget(QWidget):
    clicked = pyqtSignal(str, QWidget)

    def __init__(self, svg_path, node_name, parent=None):
        super().__init__(parent)
        self.svg_path = svg_path
        self.renderer = QSvgRenderer(svg_path)
        self.renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.setMinimumSize(400, 400)  # Angepasst an Grid
        self.setMaximumSize(600, 600)
        self.node_name = node_name
        
        self._scale = 1.0
        self.animation = QPropertyAnimation(self, b"scale")
        self.animation.setDuration(700)  # Duration in ms
        self.animation.setKeyValues([
            (0.0, 1.0),
            (0.3, 1.05),
            (1.0, 1.0),
        ])
        self.animation.setEasingCurve(QEasingCurve.Type.OutBounce)

        self.setMouseTracking(False)

    @pyqtProperty(float)
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, value):
        self._scale = value
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.node_name, self)
        super().mousePressEvent(event)

    def playAnimation(self):
        self.animation.stop()
        self.animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if hasattr(self, '_scale') and self._scale != 1.0:
            center_x = self.width() / 2.0
            center_y = self.height() / 2.0
            
            painter.translate(center_x, center_y)
            painter.scale(self._scale, self._scale)
            painter.translate(-center_x, -center_y)
        
        self.renderer.render(painter, QRectF(self.rect()))
        painter.end()