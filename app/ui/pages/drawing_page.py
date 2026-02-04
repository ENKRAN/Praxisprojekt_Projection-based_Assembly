import tempfile
from pathlib import Path
import numpy as np
import cv2

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QGraphicsView, QSlider
)
from PyQt6.QtGui import QPixmap, QColor, QImage
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView

from app.ui.components.drawing.zoomable_view import ZoomableView
from app.ui.components.drawing.interactive_scene import InteractiveScene
from app.utils.svg_utils import generateSVGfromDrawing, optimizeSVG

class DrawingPage(QWidget):
    """
    The central widget for drawing.
    It manages the scene and the view, but delegates Toolbar-Control to the MainWindow.
    """
    # Signal emits the path to the temporary SVG file when user clicks Save
    save_clicked = pyqtSignal(str) 
    # Signal to cancel/go back
    cancel_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Internal State (Accessed by InteractiveScene via parent())
        self.bg_pixmap = None
        self.bg_item = None
        
        # Drawing Attributes (Controlled by MainWindow)
        self.current_tool = 'brush'
        self.pen_color = QColor(Qt.GlobalColor.white)
        self.pen_width = 3
        self.fill_shape = False
        self.text_size = 24
        self.show_radius = False 

        self.initUI()
        
    def initUI(self):
        # Layout: Horizontal (Slider | DrawingView | Flowchart)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 1. Size Slider (Vertical, Left)
        self.size_slider = QSlider(Qt.Orientation.Vertical)
        self.size_slider.setRange(1, 50)
        self.size_slider.setValue(self.pen_width)
        self.size_slider.valueChanged.connect(self.handleBrushSizeChange)
        self.styleSlider(self.size_slider)
        layout.addWidget(self.size_slider)

        # 2. Drawing View (Center)
        # We start with a default size, will be updated in loadSnapshot
        self.scene = InteractiveScene(0, 0, 1280, 720, parent=self)
        self.view = ZoomableView(self.scene, self)
        
       
        self.view.setFixedSize(1280, 720)
        layout.addWidget(self.view, stretch=1)
        
        # 3. Flowchart/Help View (Right)
        self.flowchart_widget = QWebEngineView()
        self.flowchart_widget.setMaximumWidth(200)
        self.flowchart_widget.setMaximumHeight(400)

        # Initialize with empty dark page
        layout.addWidget(self.flowchart_widget)
        self.flowchart_widget.setHtml('<html><body style="background-color: #2e3440;"></body></html>')
        
        self.setLayout(layout)

    def loadSnapshot(self, cv_image: np.ndarray):
        """
        Loads the snapshot (OpenCV BGR Array) into the scene.
        Called by MainWindow before switching to this page.
        """
        # Convert CV BGR to QImage
        height, width, channel = cv_image.shape
        bytes_per_line = 3 * width
        q_img = QImage(cv_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
        self.bg_pixmap = QPixmap.fromImage(q_img)
        
        # Clear previous items
        self.scene.clear()
        
        # Set Background
        self.scene.setSceneRect(0, 0, width, height)
        self.bg_item = self.scene.addPixmap(self.bg_pixmap)
        self.bg_item.setZValue(-100) # Ensure background is behind everything
        
        # Fit view to new image
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # --- Public Methods called by MainWindow Toolbars ---

    def setTool(self, tool_key: str):
        """Called when a tool button is clicked in MainWindow."""
        self.current_tool = tool_key
        
        if tool_key == 'select':
            self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        # Clear selection when switching tools
        self.scene.clearSelection()

    def setPenColor(self, color: QColor):
        """Called when color is picked."""
        self.pen_color = color
        self.scene.update()

    def setFillShape(self, enabled: bool):
        """Called when Fill Checkbox is toggled."""
        self.fill_shape = enabled

    def deleteSelected(self):
        """Deletes selected items."""
        for item in self.scene.selectedItems():
            self.scene.removeItem(item)

    def handleBrushSizeChange(self, value):
        """Internal slot for the slider."""
        self.pen_width = value
        self.show_radius = True
        self.scene.update()

    def saveStep(self):
        """
        Generates the SVG, saves it to a temp file, and emits the signal.
        The MainWindow catches the signal and handles the persistent storage.
        """
        temp_svg = tempfile.NamedTemporaryFile(delete=False, suffix=".svg")
        temp_svg.close()
        save_path = Path(temp_svg.name)
        
        try:
            # Generate SVG using your utility
            generateSVGfromDrawing(save_path, self.bg_pixmap, self.bg_item, self.scene)
            optimizeSVG(save_path)
            
            # Inform MainWindow
            self.save_clicked.emit(str(save_path))
            
        except Exception as e:
            print(f"Error saving SVG: {e}")

    def styleSlider(self, slider):
        """Applies the custom CSS to the slider."""
        slider.setStyleSheet("""
            QSlider::groove:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #B1B1B1, stop:1 #c4c4c4);
                border: 1px solid #999999; width: 20px; border-radius: 10px;
            }
            QSlider::handle:vertical {
                background: #535c8f; height: 20px; margin: 0 -5px; border-radius: 10px;
            }
        """)