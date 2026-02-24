import tempfile
from pathlib import Path
import numpy as np
import cv2

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QGraphicsView, QSlider, QGraphicsTextItem, QApplication
)
from PyQt6.QtGui import QPixmap, QColor, QImage, QTextCharFormat, QBrush
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView

from app.ui.components.drawing.zoomable_view import ZoomableView
from app.ui.components.drawing.interactive_scene import InteractiveScene
from app.utils.svg_utils import generateSVGfromDrawing, optimizeSVG
from app.ui.components.drawing.interactive_scene import EditableTextItem

class DrawingPage(QWidget):
    """
    The central widget for drawing.
    It manages the scene and the view, but delegates Toolbar-Control to the MainWindow.
    """
    # Signal emits the path to the temporary SVG file when user clicks Save
    save_clicked = pyqtSignal(str) 
    cancel_clicked = pyqtSignal()
    tool_selected = pyqtSignal(str)
    selection_changed = pyqtSignal(int)

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
        self.size_slider = QSlider(Qt.Orientation.Vertical, self)
        self.size_slider.setRange(1, 100)
        self.size_slider.setValue(self.pen_width)
        self.size_slider.setMinimumSize(80, 300)
        self.size_slider.setMaximumSize(120, 500) 
        self.size_slider.valueChanged.connect(self.handleBrushSizeChange)

        self.size_slider.setStyleSheet("""
            QSlider::groove:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #B1B1B1, stop:1 #c4c4c4);
                border: 1px solid #999999;
                width: 50px;
                border-radius: 25px;
                margin: 0 0;
            }

            QSlider::add-page:vertical,
            QSlider::sub-page:vertical {
                background: transparent;
                border: none;
            }

            QSlider::handle:vertical {
                background: #535c8f;
                width: 50px;
                height: 50px;
                margin: -2px 0px;
                border: 2px solid #a8acbf;
                border-radius: 25px;
            }

            QSlider::handle:vertical:hover {
                background: #838fd6;
                border-color: #4f5159;
            }
        """)
        layout.addWidget(self.size_slider, stretch=0)

        # 2. Drawing View (Center)
        # We start with a default size, will be updated in loadSnapshot
        self.scene = InteractiveScene(0, 0, 1280, 720, parent=self)
        self.view = ZoomableView(self.scene, self)
        
        self.scene.selectionChanged.connect(self.onSelectionChanged)
       
        self.view.setFixedSize(1280, 720)
        layout.addWidget(self.view, stretch=1)
        
        # 3. Flowchart/Help View (Right)
        self.flowchart_widget = QWebEngineView()
        # self.flowchart_widget.setMaximumWidth(200)
        # self.flowchart_widget.setMaximumHeight(1000)

        # Initialize with empty dark page
        layout.addWidget(self.flowchart_widget, 0)
        self.flowchart_widget.setHtml('<html><body style="background-color: #2e3440;"></body></html>')
        
        self.setLayout(layout)

    def onSelectionChanged(self):
        num_selected = len(self.scene.selectedItems())
        self.selection_changed.emit(num_selected)

    def loadSnapshot(self, cv_image: np.ndarray):
        """
        Loads the snapshot (OpenCV BGR Array) into the scene.
        """
        # 1. Convert BGR (OpenCV) to RGB (Qt)
        # We use the same robust logic as in VisionWorker
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        
        height, width, channel = rgb_image.shape
        bytes_per_line = channel * width
        
        # 2. Create QImage
        # .copy() is crucial to ensure QImage owns the data and doesn't crash 
        # if the numpy array gets garbage collected later.
        q_img = QImage(rgb_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).copy()
        
        self.bg_pixmap = QPixmap.fromImage(q_img)
        
        # 3. Setup Scene
        self.scene.clear()
        # self.scene.setSceneRect(0, 0, width, height)
        self.bg_item = self.scene.addPixmap(self.bg_pixmap)
        self.bg_item.setPos(0, 0)
        self.bg_item.setZValue(0)
        
        self.view.setFixedSize(self.bg_pixmap.width(), self.bg_pixmap.height())

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

        for item in self.scene.items():
            if isinstance(item, QGraphicsTextItem):
                if tool_key != 'text':
                    item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        self.tool_selected.emit(tool_key)

    def setPenColor(self, color_hex_string: str):
        """
        Handles color selection from the palette and updates the pen color.
        Applies the new color to the selected text or the current cursor format.
        """
        new_color = QColor(color_hex_string)
        self.pen_color = new_color

        # Check if a text item is currently being edited
        focused_item = self.scene.focusItem()
        if isinstance(focused_item, EditableTextItem):
            cursor = focused_item.textCursor()
            char_format = QTextCharFormat()
            char_format.setForeground(QBrush(new_color))
            cursor.mergeCharFormat(char_format)
        else:
            # Apply to all selected text items if no item is being edited
            for item in self.scene.selectedItems():
                if isinstance(item, QGraphicsTextItem):
                    item.setDefaultTextColor(new_color)
        
        self.scene.update()

    def toggleFillShape(self, checked):
        """
        Toggles the fill shape option for rectangle and circle tools.

        Args:
            checked (bool): True if fill shape should be enabled, False otherwise.
        """
        self.fill_shape = checked
        self.scene.update()

    def deleteSelected(self):
        """Deletes selected items."""
        for item in self.scene.selectedItems():
            self.scene.removeItem(item)

    def handleBrushSizeChange(self, value):
        """Internal slot for the slider."""
        self.pen_width = value
        self.show_radius = True
        self.scene.update()

    def handleTextSizeChange(self, value):
        """
        Updates the text size for the text tool.
        Applies the new size to the selected text or the current cursor format.
        """
        self.text_size = value
        
        # Check if a text item is currently being edited
        focused_item = self.scene.focusItem()
        if isinstance(focused_item, EditableTextItem):
            cursor = focused_item.textCursor()
            char_format = QTextCharFormat()
            char_format.setFontPointSize(float(value))
            cursor.mergeCharFormat(char_format)
        else:
            # Apply to all selected text items if no item is being edited
            for item in self.scene.selectedItems():
                if isinstance(item, QGraphicsTextItem):
                    font = item.font()
                    font.setPointSize(value)
                    item.setFont(font)

    def saveStep(self):
        """
        Generates the SVG, saves it to a temp file, and emits the signal.
        The MainWindow catches the signal and handles the persistent storage.
        """
        # Debug: Print DPI for troubleshooting scaling issues
        screen = QApplication.primaryScreen()
        dpi = screen.physicalDotsPerInch()
        print(f"DPI: {dpi}")

        # ---------------------------------------------------

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

    def load_svg(self, svg_path):
        """Lädt das SVG, versteckt Scrollbalken und aktiviert natives Touch-Panning & Pinch-to-Zoom."""
        abs_path = svg_path.resolve()
        html = f"""
        <html>
          <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
            <style>
              /* Hässliche Scrollbalken ausblenden */
              ::-webkit-scrollbar {{
                  display: none;
              }}
              body {{
                  background-color: #2e3440;
                  margin: 0;
                  padding: 20px;
                  overflow: auto; 
                  /* Übergibt die Kontrolle komplett an das native Chromium-Touch-System */
                  touch-action: pan-x pan-y pinch-zoom; 
              }}
              .svg-container {{
                  transform: scale(1.3); /* Startgröße */
                  transform-origin: top left;
              }}
            </style>
          </head>
          <body>
            <div class="svg-container">
                <embed src="{abs_path}" type="image/svg+xml" style="max-width: none;" />
            </div>
          </body>
        </html>
        """
        self.flowchart_widget.setHtml(html, QUrl.fromLocalFile(str(abs_path.parent)))
