from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication,
    QSlider, 
    QWidgetAction, 
    QGraphicsView,
    QGraphicsTextItem,
    QWidget,
    QHBoxLayout
)
from PyQt6.QtGui import QPixmap, QColor, QBrush, QTextCharFormat
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView

from app.ui.components.drawing.zoomable_view import ZoomableView
from app.ui.components.drawing.interactive_scene import InteractiveScene, EditableTextItem
from app.utils.svg_utils import generateSVGfromDrawing, optimizeSVG

class DrawingPage(QWidget):
    """
    A drawing tool application that allows users to draw shapes on a background image.
    Args:
        input_path (str): Path to the input image file.
        output_dir (str): Directory where the output image will be saved.
    """
    save_clicked = pyqtSignal(str) # Emits the path to the temp SVG file
    cancel_clicked = pyqtSignal()

    def __init__(self, input_path, output_dir, parent=None):
        super().__init__(parent)
        self.main_window = parent

        try:
            self.bg = QPixmap(input_path)
            print(f"Size of Image to be drawn on: ", self.bg.size())
        except Exception as e:
            self.bg = QPixmap(1280, 720); self.bg.fill(QColor("darkslategray"))

        # Create a scene for drawing
        self.scene = InteractiveScene(0, 0, self.bg.width(), self.bg.height(), parent=self)

        # Add the background image to the scene
        self.bg_item = self.scene.addPixmap(self.bg)
        self.bg_item.setPos(0, 0)
        self.bg_item.setZValue(0)

        # Create a transparent view for displaying the drawing layer
        self.view = ZoomableView(self.scene, self)
        self.view.setFixedSize(self.bg.width(), self.bg.height())

        self._initUI()

        # Path info for saving
        self.output_dir = Path(output_dir)
        base = Path(input_path)
        self.input_name = base.stem
        
        init_html = """<html>
          <body style="background-color: #2e3440;">
          </body>
        </html>"""

        self.flowchart_widget.setHtml(init_html)

    def _initUI(self):
        layout = QHBoxLayout(self)

        self.tools = {
            'select': 'Select',
            'scale': 'Scale',
            'erase': 'Erase',
            'nodes': 'Nodes',
            'brush': 'Brush',
            'rectangle': 'Rectangle',
            'circle': 'Circle',
            'arrow': 'Arrow',
            'text': 'Text'
        }

        # Base drawing states
        self.current_tool = 'brush'
        self.pen_color = QColor(Qt.GlobalColor.white)
        self.pen_width = 2
        self.show_radius = False
        self.fill_shape = False
        self.text_size = 12 

        # Slider
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

        self.flowchart_widget = QWebEngineView()
        self.flowchart_widget.setMinimumWidth(200)
        self.flowchart_widget.setMaximumWidth(400)

        layout.addWidget(self.size_slider, 0)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.flowchart_widget, 0)
        self.setLayout(layout)

    def showEvent(self, event):
        """
        Fit the scene in the view when the widget is first shown.
        """
        # self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        super().showEvent(event)

    def onSelectionChanged(self):
        """
        Updates the visibility of the delete action based on the number of selected items.
        """
        num_selected = len(self.scene.selectedItems())
        self.main_window.delete_action.setVisible(num_selected >= 1)

    def selectTool(self, tool):
        """
        Selects the drawing tool and updates the UI accordingly.

        Args:
            tool (str): The tool to select, one of 'brush', 'rectangle', 'circle', 'arrow'.
        """
        # Change tool
        self.current_tool = tool

        if tool == 'select':
            self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)

        # Reset the scene to ensure no items are selected
        self.scene.clearSelection()

        for item in self.scene.items():
            if isinstance(item, QGraphicsTextItem):
                if tool != 'text':
                    item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        # Update buttons visually
        for action in self.main_window.tools_toolbar.actions():
            if not isinstance(action, QWidgetAction) and action.text() in ['Select', 'Scale', 'Erase', 'Nodes', 'Brush','Rectangle','Circle','Arrow', 'Text']: # Check if not QWidgetAction
                action.setChecked(action.text() == {'select':'Select', 'scale':'Scale', 'erase':'Erase', 'nodes':'Nodes', 'brush':'Brush', 'rectangle':'Rectangle', 'circle':'Circle', 'arrow':'Arrow', 'text':'Text'}[tool])

        # Enable/disable fill_action based on the selected tool
        if self.current_tool in ['brush', 'rectangle', 'circle']:
            self.main_window.fill_action.setEnabled(True)
        else:
            self.main_window.fill_action.setEnabled(False)
            self.main_window.fill_shape_checkbox.setChecked(False) 
            if self.fill_shape:  # only update if it was true
                self.fill_shape = False

    def deleteSelectedItems(self):
        """
        Deletes all selected items from the scene.
        """
        for item in self.scene.selectedItems():
            self.scene.removeItem(item)

    def toggleFillShape(self, checked):
        """
        Toggles the fill shape option for rectangle and circle tools.

        Args:
            checked (bool): True if fill shape should be enabled, False otherwise.
        """
        self.fill_shape = checked
        self.scene.update()  # Update the scene to reflect the change

    def handlePaletteSelection(self, color_hex_string):
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

    def handleBrushSizeChange(self, value):
        """
        Updates brush thickness and shows preview.

        Args:
            value (int): The new thickness value for the brush.
        """
        self.pen_width = value
        self.show_radius = True
        if hasattr(self, 'scene') and self.scene:
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

    def finishAndSave(self):
        """
        Finishes the drawing session and saves the current scene as an SVG file.
        """
        screen = QApplication.primaryScreen()
        dpi = screen.physicalDotsPerInch()
        print(f"DPI: {dpi}")

        save_path = self.output_dir / f"{self.input_name}_drawn.svg"
        generateSVGfromDrawing(save_path, self.bg, self.bg_item, self.scene)
        optimizeSVG(save_path)

        if self.main_window.flowchart_page.output_svg_path.exists():
            try:
                self.main_window.flowchart_page.output_svg_path.unlink()
            except Exception as e:
                print(f"Error deleting existing Flowchart SVG file: {e}")
        else:
            print("No existing Flowchart SVG file to delete.")

        self.parent().setCurrentIndex(1)

    def resetToolbars(self):
        self.main_window.tools_toolbar.show()
        self.main_window.fill_shape_toolbar.show()
        self.main_window.colors_toolbar.show()
        self.main_window.save_button_toolbar.show()