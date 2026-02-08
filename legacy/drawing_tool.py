import math
from pathlib import Path
import shutil
from pyflowchart import *
import tempfile
import subprocess
from scour import scour
import sys
import argparse

# Test imports for profiling
import cProfile
import io
import pstats
import time

from PyQt6.QtSvg import QSvgGenerator, QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication, 
    QMainWindow, 
    QPushButton, 
    QToolBar, 
    QSlider, 
    QCheckBox,
    QSpinBox, 
    QWidgetAction, 
    QGraphicsScene, 
    QGraphicsView, 
    QGraphicsRectItem, 
    QGraphicsEllipseItem, 
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsTextItem,
    QStackedWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGridLayout,
    QDialog,
    QGraphicsDropShadowEffect,
    QSizePolicy
)
from PyQt6.QtGui import QPainter, QPixmap, QPen, QColor, QBrush, QIcon, QPainterPath, QTransform, QFont, QTextCharFormat, QAction, QFontMetrics
from PyQt6.QtCore import Qt, QPoint, QSize, QRectF, QPointF, QRect, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty, QTimer, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from legacy.palette import PaletteHorizontal, PALETTES, PaletteGrid
from PyQt6.QtWidgets import QLineEdit

def profiliere_funktion(func, *args, **kwargs):
    """
    Führt die übergebene Funktion mit ihren Parametern aus und profiliert deren Ausführung.
    Gibt einen formatierten Profiling-Bericht zurück.

    Args:
        func (callable): Die Funktion, die profiliert werden soll.
        *args: Positionsargumente, die an 'func' übergeben werden.
        **kwargs: Schlüsselwortargumente, die an 'func' übergeben werden.
    """
    profiler = cProfile.Profile()

    # Profiling starten
    profiler.enable()

    # Die zu profilierende Funktion mit ihren Parametern ausführen
    try:
        func(*args, **kwargs) # <- Hier werden die Parameter übergeben!
    finally:
        # Profiling stoppen, auch wenn ein Fehler auftritt
        profiler.disable()

    # Profiling-Daten verarbeiten und formatieren
    s = io.StringIO()
    sortby = 'cumtime'
    ps = pstats.Stats(profiler, stream=s).sort_stats(sortby)
    ps.print_stats(10)
    return s.getvalue()

class ZoomableView(QGraphicsView):
    """
    A subclass of QGraphicsView that implements zoom and pan functionality.

    Args:
        scene (QGraphicsScene): The scene to be displayed in the view.
        parent (QWidget, optional): The parent widget. Defaults to None.
    """
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)

        # Important settings for a good user experience
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Apply settings from the original code
        self.setStyleSheet("background: transparent;")
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)

        self.min_zoom_level = 0.2  # Minimum zoom (e.g., 10%)
        self.max_zoom_level = 10.0   # Maximum zoom (e.g., 1000%)

    def wheelEvent(self, event):
        """
        This method is called when the mouse wheel is scrolled.

        Args:
            event (QWheelEvent): The wheel event that triggered this method.
        """
        # Read the current zoom factor from the view's transformation matrix
        # m11() is the horizontal scaling factor. Since we scale proportionally,
        # this value is identical to the vertical one (m22).
        current_zoom = self.transform().m11()

        # Define zoom factor
        zoom_factor = 1.15

        # Evaluate mouse wheel scroll direction
        if event.angleDelta().y() > 0:
            # Check if the upper limit is exceeded
            # Zoom in only if the maximum has not yet been reached.
            if current_zoom * zoom_factor <= self.max_zoom_level:
                self.scale(zoom_factor, zoom_factor)
        else:
            # Check if the lower limit is undershot
            # Zoom out only if the minimum has not yet been reached.
            if current_zoom / zoom_factor >= self.min_zoom_level:
                self.scale(1 / zoom_factor, 1 / zoom_factor)

class InteractiveScene(QGraphicsScene):
    def __init__(self, x, y, width, height, parent=None):
        super().__init__(x, y, width, height, parent)

        self.drawing_window = parent

        self.drawing_shape = False
        self.start_pos = QPointF()
        self.last_pos = QPointF()

        self.temp_rect_ref = None
        self.temp_ellipse_ref = None 
        self.temp_arrow_ref = None
        self.temp_path_ref = None

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)

        if self.drawing_window.show_radius:
            if self.views():
                view = self.views()[0] 

                center_scene_pos = view.mapToScene(view.viewport().rect().center())

                is_pen_color_dark = (self.drawing_window.pen_color.red() * 0.299 + self.drawing_window.pen_color.green() * 0.587 + self.drawing_window.pen_color.blue() * 0.114) < 128
                border_preview_color = QColor(Qt.GlobalColor.white) if is_pen_color_dark else QColor(Qt.GlobalColor.black)
                border_preview_color.setAlpha(200) 

                preview_pen = QPen(border_preview_color, 1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                painter.setPen(preview_pen)
                painter.setBrush(QBrush(self.drawing_window.pen_color))

                radius = self.drawing_window.pen_width / 2.0

                painter.drawEllipse(center_scene_pos, radius, radius)

                self.drawing_window.show_radius = False
            else:
                self.drawing_window.show_radius = False

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.drawing_window.current_tool == 'erase':
            self.eraseAt(event.scenePos())
            return 

        if self.drawing_window.current_tool == 'select' or self.drawing_window.current_tool == 'scale':
            super().mousePressEvent(event)
            return

        if self.drawing_window.current_tool == 'text':
            pos = event.scenePos()
            transform = self.views()[0].transform() if self.views() else QTransform()
            item = self.itemAt(pos, transform)

            if isinstance(item, QGraphicsTextItem):
                item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
                item.setFocus()
                super().mousePressEvent(event)
                return

            self.text_item = EditableTextItem()
            self.text_item.setPos(pos)
            self.text_item.setDefaultTextColor(self.drawing_window.pen_color)
            self.text_item.setFont(QFont(self.drawing_window.font().family(), self.drawing_window.text_size))

            self.addItem(self.text_item)
            self.text_item.setFocus()
            return

        self.start_pos = event.scenePos()
        self.drawing_shape = True

        if self.drawing_window.current_tool == 'brush':
            path = QPainterPath(QPointF(0,0))
            self.temp_path_ref = QGraphicsPathItem(path)
            self.temp_path_ref.setPen(QPen(self.drawing_window.pen_color, self.drawing_window.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

            self.temp_path_ref.setPos(self.start_pos)

            self.addItem(self.temp_path_ref)
        elif self.drawing_window.current_tool == 'rectangle':
            temp_rect = QGraphicsRectItem(0, 0, 0, 0)
            temp_rect.setPen(QPen(self.drawing_window.pen_color, self.drawing_window.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

            if self.drawing_window.fill_shape:
                temp_rect.setBrush(QBrush(self.drawing_window.pen_color))

            temp_rect.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
            self.addItem(temp_rect)

            self.temp_rect_ref = temp_rect
        elif self.drawing_window.current_tool == 'circle':
            temp_ellipse = QGraphicsEllipseItem(0, 0, 0, 0)
            temp_ellipse.setPen(QPen(self.drawing_window.pen_color, self.drawing_window.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

            if self.drawing_window.fill_shape:
                temp_ellipse.setBrush(QBrush(self.drawing_window.pen_color))

            temp_ellipse.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
            self.addItem(temp_ellipse)

            self.temp_ellipse_ref = temp_ellipse
        elif self.drawing_window.current_tool == 'arrow':
            temp_arrow = QGraphicsPathItem()
            temp_arrow.setPen(QPen(self.drawing_window.pen_color, self.drawing_window.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            temp_arrow.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
            self.addItem(temp_arrow)

            self.temp_arrow_ref = temp_arrow

    def mouseMoveEvent(self, event):
        if self.drawing_window.current_tool == 'erase' and event.buttons() == Qt.MouseButton.LeftButton:
            self.eraseAt(event.scenePos())
            return

        if not self.drawing_shape:
            if self.drawing_window.current_tool == 'select':
                super().mouseMoveEvent(event)
            return
        
        self.last_pos = event.scenePos()

        x = min(self.start_pos.x(), self.last_pos.x())
        y = min(self.start_pos.y(), self.last_pos.y())
        width = abs(self.last_pos.x() - self.start_pos.x())
        height = abs(self.last_pos.y() - self.start_pos.y())

        if self.drawing_window.current_tool == 'scale':
            pass # TODO: Implement scaling logic here

        if self.drawing_window.current_tool == 'brush' and self.temp_path_ref:
            path = self.temp_path_ref.path()

            local_point = self.temp_path_ref.mapFromScene(self.last_pos)
            path.lineTo(local_point)
            self.temp_path_ref.setPath(path)
        elif self.drawing_window.current_tool == 'rectangle' and self.temp_rect_ref:

            self.temp_rect_ref.setRect(x, y, width, height)
        elif self.drawing_window.current_tool == 'circle' and self.temp_ellipse_ref:
            self.last_pos = event.scenePos()

            self.temp_ellipse_ref.setRect(x, y, width, height)
        elif self.drawing_window.current_tool == 'arrow' and self.temp_arrow_ref:
            self.last_pos = event.scenePos()

            # Create a path for the arrow
            path = QPainterPath()
            p1 = self.start_pos
            p2 = self.last_pos
            path.moveTo(p1)
            path.lineTo(p2)

            # Draw arrowhead
            angle = math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
            size  = self.drawing_window.pen_width * 4  # Size of the arrowhead
            for sign in (1, -1):
                theta = angle + sign * math.radians(20)
                x = p2.x() - size * math.cos(theta)
                y = p2.y() - size * math.sin(theta)
                path.moveTo(p2)
                path.lineTo(QPointF(x, y))

            self.temp_arrow_ref.setPath(path)
                
    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.drawing_window.current_tool == 'erase':
            return

        if self.drawing_window.current_tool == 'select' or self.drawing_window.current_tool == 'scale':
            super().mouseReleaseEvent(event)
            return
        
        if not self.drawing_shape:
            return

        if self.drawing_window.current_tool == 'brush' and self.temp_path_ref:
            final_path_local = self.temp_path_ref.path()
            item_pos_in_scene = self.temp_path_ref.pos()

            editable_item = QGraphicsPathItem(final_path_local)
            editable_item.setFlags(
                QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            )
            editable_item.setPen(self.temp_path_ref.pen())
            editable_item.setPos(item_pos_in_scene)

            if self.drawing_window.fill_shape:
                editable_item.setBrush(self.drawing_window.pen_color)

            self.removeItem(self.temp_path_ref)
            self.addItem(editable_item)

            self.temp_path_ref = None
        else:
            self.temp_rect_ref = None
            self.temp_ellipse_ref = None
            self.temp_arrow_ref = None

        self.drawing_shape = False

    def eraseAt(self, position):
        """
        Erases the item at the given position in the scene.

        Args:
            position (QPointF): The position in the scene where the item should be erased.
        """
        transform = self.views()[0].transform() if self.views() else QTransform()
        item_to_erase = self.itemAt(position, transform)
        if item_to_erase and item_to_erase != self.drawing_window.bg_item:
            self.removeItem(item_to_erase)

class EditableTextItem(QGraphicsTextItem):
    def __init__(self):
        super().__init__()

        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        if self.scene() and not self.toPlainText().strip():
            self.scene().removeItem(self)
        super().focusOutEvent(event)

class DrawingTool(QWidget):
    """
    A drawing tool application that allows users to draw shapes on a background image.
    Args:
        input_path (str): Path to the input image file.
        output_dir (str): Directory where the output image will be saved.
    """
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

        # Create a transparent view for displaying the drawing layer
        self.view = ZoomableView(self.scene, self)

        self.view.setFixedSize(self.bg.width(), self.bg.height())
        
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
        self.size_slider.setMinimumSize(80, 300)   # Kleinere Mindestgröße
        self.size_slider.setMaximumSize(120, 500)   # Maximale Größe begrenzen
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
        init_html = """<html>
          <body style="background-color: #2e3440;">
          </body>
        </html>"""

        layout.addWidget(self.size_slider, 0)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.flowchart_widget, 0)
        self.setLayout(layout)

        # Path info for saving
        self.output_dir = Path(output_dir)
        base = Path(input_path)
        self.input_name = base.stem
        
        self.flowchart_widget.setHtml(init_html)

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
        gen = QSvgGenerator()
        gen.setResolution(96)
        gen.setFileName(str(save_path))
        gen.setSize(QSize(self.bg.width(), self.bg.height()))                       
        scene_rect = self.scene.sceneRect()
        gen.setViewBox(QRect(int(scene_rect.x()), int(scene_rect.y()), int(scene_rect.width()), int(scene_rect.height())))    
        gen.setTitle("Vektor-Editor Export")
        gen.setDescription("SVG export from PyQt6 QGraphicsScene")

        # For text to path conversion
        temp_path_items = []
        original_text_items = []

        for item in list(self.scene.items()):
            if isinstance(item, QGraphicsTextItem) and item.isVisible() and item.toPlainText().strip():
                # 1. Copy properties
                font = item.font()
                text = item.toPlainText()
                color = item.defaultTextColor()
                z_value = item.zValue()

                # 2. Create raw path from text
                raw_path = QPainterPath()
                fm = QFontMetrics(font)
                baseline_offset = fm.ascent()
                raw_path.addText(0, baseline_offset, font, text)

                # Apply the item's transformation to get absolute coordinates
                transform_matrix = item.sceneTransform()
                
                # map() applies the matrix to every point in the path
                absolute_path = transform_matrix.map(raw_path)

                # 3. Create PathItem with the absolute path
                path_item = QGraphicsPathItem(absolute_path)
                path_item.setPen(QPen(Qt.PenStyle.NoPen)) 
                path_item.setBrush(QBrush(color))
                
                # The item itself is now at 0,0, because the coordinates are shifted within the path itself.
                path_item.setPos(0, 0) 
                
                # Maintain the original z-value
                path_item.setZValue(z_value)

                # 4. Perform the swap
                self.scene.addItem(path_item)
                item.hide()
                
                temp_path_items.append(path_item)
                original_text_items.append(item)

        painter = QPainter(gen)

        # 1) Fill the background with black, to ensure that the projected image has a transparent background
        painter.fillRect(self.scene.sceneRect(), Qt.GlobalColor.black)

        # 2) Temporarily hide the background item to prevent it from being painted
        self.bg_item.setVisible(False)

        # 3) Deselect all selected items to avoid rendering selection frames
        if self.scene.selectedItems():
            for it in list(self.scene.selectedItems()):
                it.setSelected(False)

        # 4) Render the scene (now only draws your shapes)
        self.scene.render(painter)

        painter.end()

        # 5) Restore the background item
        self.bg_item.setVisible(True)

        print(f"Saved SVG: {save_path}")

        self.optimizeSVG(save_path)

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

    def optimizeSVG(self, svg_file_path):
        with open(svg_file_path, "r", encoding="utf-8") as f:
            original_svg_code = f.read()

        options = scour.sanitizeOptions()
        options.remove_metadata        = False
        options.remove_titles          = False
        options.remove_descriptions    = False
        options.keep_editor_data       = True
        options.keep_unreferenced_defs = True
        options.enable_viewboxing      = False
        options.enable_id_stripping    = False
        options.shorten_ids            = False
        options.indent_type            = "space"
        options.nindent                = 1

        optimized_svg_code = scour.scourString(original_svg_code, options)

        with open(svg_file_path, "w", encoding="utf-8") as f:
            f.write(optimized_svg_code)

        print(f"SVG reduced from {len(original_svg_code)} to {len(optimized_svg_code)} bytes")

class MainWindow(QMainWindow):
    editor_closed_signal = pyqtSignal()

    def __init__(self, input_path, output_dir):
        super().__init__()

        self.diagrams_tool_path = shutil.which("diagrams")
        if not self.diagrams_tool_path:
            print("Error: The 'diagrams' tool was not found in the system PATH.")
            print("Please make sure that Node.js is installed and you have installed '@diagrams/cli' globally (npm install -g @diagrams/cli@latest).")
            print("You may also need to restart your terminal and VS Code or restart your system for the PATH to be recognized correctly.")
            return
        
        self.current_flowchart_node = None
        self.current_flowchart_branch = "main"
        self.branch_counter = 1

        self.branches_dict = {
            self.current_flowchart_branch: "Active"
        }

        self.branches_order = [self.current_flowchart_branch]

        # To check which condition node exists on which branch
        self.condition_nodes_to_branches = { 
            self.current_flowchart_branch: [] 
        }

        self.setWindowTitle("Drawing Tool")

        self.setStyleSheet("""
            QMainWindow {
                background-color: #2e3440;
            }
            QToolBar {
                background-color: #4c566a;
            }
            QWidget#shadow_widget {
                background-color: #2e3440;
                border-radius: 15px;
            }
            QPushButton {
                background-color: #414a5c; 
                color: white; 
                border: 2px solid #d8dee9;
                border-radius: 15px;
            }
            QPushButton:pressed {
                background-color: #3b4252;
            }
        """)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Create all pages first
        self.flowchart_page = FlowchartPage(self)
        self.drawing_tool = DrawingTool(input_path, output_dir, self)
        self.start_page = StartPage(self)

        # Add them to the stacked widget
        self.stacked_widget.addWidget(self.start_page)
        self.stacked_widget.addWidget(self.flowchart_page)
        self.stacked_widget.addWidget(self.drawing_tool)

        self.stacked_widget.currentChanged.connect(self.onPageChanged)

        self.initToolbars()

        self.drawing_tool.scene.selectionChanged.connect(self.drawing_tool.onSelectionChanged)

        self.showFullScreen()

        self.onPageChanged(0)

    def initToolbars(self):
        ### --- Tools Toolbars ---

        # Toolbar for tools like brush, rectangle, circle, arrow
        self.tools_toolbar = QToolBar("Tools")

        # Actions for tool shapes
        for tool, text in self.drawing_tool.tools.items():
            action = QAction(text, self)
            action.setCheckable(True)
            action.setIcon(QIcon(f"legacy/resources/{tool}.svg"))
            action.triggered.connect(lambda checked, t=tool: self.drawing_tool.selectTool(t))
            self.tools_toolbar.addAction(action)
            if tool == 'brush':
                action.setChecked(True)

        self.tools_toolbar.setIconSize(QSize(64, 64))  # Kleinere Icons

        self.text_size_spinbox = QSpinBox(self)
        self.text_size_spinbox.setRange(1, 50)
        self.text_size_spinbox.setValue(self.drawing_tool.text_size)  # Default text size
        self.text_size_spinbox.setSuffix(" pt")
        self.text_size_spinbox.setStyleSheet("""
            QSpinBox {
                font-size: 24px;
                padding: 5px;
                min-height: 40px;
                border: 2px solid #4c566a;
                border-radius: 5px;
                background-color: #d8dee9;
                color: #2e3440;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 25px;
                height: 20px;
            }
        """)
        self.text_size_spinbox.valueChanged.connect(self.drawing_tool.handleTextSizeChange)

        self.text_size_action = QWidgetAction(self)
        self.text_size_action.setDefaultWidget(self.text_size_spinbox)
        self.tools_toolbar.addAction(self.text_size_action)

        self.tools_toolbar.addSeparator()

        self.delete_action = QAction("Delete", self)
        self.delete_action.setIcon(QIcon("legacy/resources/delete.svg")) 
        self.delete_action.triggered.connect(self.drawing_tool.deleteSelectedItems)
        self.tools_toolbar.addAction(self.delete_action)
        self.delete_action.setVisible(False)

        ### --- Fill Shape Toolbar ---

        # Toolbar for Checkbox to fill shapes
        self.fill_shape_toolbar = QToolBar("Fill Shape", self)

        # Checkbox to toggle fill shape
        self.fill_shape_checkbox = QCheckBox("Fill Shape", self)
        self.fill_shape_checkbox.setStyleSheet("QCheckBox::indicator { width: 50px; height: 50px;}")
        self.fill_shape_checkbox.setChecked(self.drawing_tool.fill_shape)
        self.fill_shape_checkbox.toggled.connect(self.drawing_tool.toggleFillShape)
        
        self.fill_action = QWidgetAction(self)
        self.fill_action.setDefaultWidget(self.fill_shape_checkbox)
        self.fill_shape_toolbar.addAction(self.fill_action)

        ### --- End of Fill Shape Toolbar ---

        ### --- Color Selection Toolbar ---

        chosen_palette_name = 'paired12' # You can choose 'paired12', 'category10', or '17undertones' here
        if chosen_palette_name in PALETTES and PALETTES[chosen_palette_name]:
            self.drawing_tool.pen_color = QColor(PALETTES[chosen_palette_name][0])
        else:
            self.drawing_tool.pen_color = QColor(Qt.GlobalColor.white) # Fallback

        # Toolbar for color selection
        self.colors_toolbar = QToolBar("Colors", self)
        
        # Use a palette from palette.py, e.g., PaletteHorizontal, PaletteGrid, or PaletteVertical
        color_palette = PaletteGrid(chosen_palette_name, n_columns=5)
        # color_palette = PaletteHorizontal(chosen_palette_name) 
        color_palette.selected.connect(self.drawing_tool.handlePaletteSelection)
        self.colors_toolbar.addWidget(color_palette)

        ### --- End of Color Selection Toolbar ---

        # Save button centered
        save_button = QPushButton("Save", self)
        save_button.setFont(QFont("Arial", 20))
        save_button.setMinimumSize(200, 100)
        save_button.clicked.connect(lambda: self.drawing_tool.finishAndSave())

        save_action = QWidgetAction(self)
        save_action.setDefaultWidget(save_button)
        self.save_button_toolbar = QToolBar("Save", self)
        self.save_button_toolbar.addAction(save_action)

        merge_branch_button = QPushButton("Merge with previous branch", self)
        merge_branch_button.setFont(QFont("Arial", 20))
        merge_branch_button.setMinimumSize(200, 100)
        merge_branch_button.clicked.connect(self.flowchart_page.mergeWithPreviousBranch)

        self.merge_branch_action = QWidgetAction(self)
        self.merge_branch_action.setDefaultWidget(merge_branch_button)
        self.merge_branch_action.setVisible(False) # Initially hidden
        self.save_button_toolbar.addAction(self.merge_branch_action)

        vertical_layout_widget = QWidget()
        vertical_layout = QVBoxLayout(vertical_layout_widget)

        fixed_branch_label = QLabel("Current Branch: ")
        fixed_branch_label.setStyleSheet("color: white; font-size: 12px;")  # TODO: REMEMBER TO SET BACK TO 42PX
        self.dynamic_branch_label = QLabel(self.current_flowchart_branch)
        self.dynamic_branch_label.setStyleSheet("color: white; font-size: 12px; margin-right: 20px;") # TODO: REMEMBER TO SET BACK TO 42PX
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        fixed_node_label = QLabel("Current Node: ")
        fixed_node_label.setStyleSheet("color: white; font-size: 12px;")  # TODO: REMEMBER TO SET BACK TO 42PX
        self.dynamic_node_label = QLabel(self.current_flowchart_node.node_name)
        self.dynamic_node_label.setStyleSheet("color: white; font-size: 12px; margin-right: 20px;") # TODO: REMEMBER TO SET_BACK TO 42PX

        vertical_layout.addWidget(fixed_branch_label)
        vertical_layout.addWidget(self.dynamic_branch_label)
        vertical_layout.addWidget(fixed_node_label)
        vertical_layout.addWidget(self.dynamic_node_label)

        self.save_button_toolbar.addWidget(spacer)
        self.save_button_toolbar.addWidget(vertical_layout_widget)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tools_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.fill_shape_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.colors_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.save_button_toolbar)

    def onPageChanged(self, index: int):
        page = self.stacked_widget.widget(index)
        page.resetToolbars()

        self.toggleMergeButton()

    def toggleMergeButton(self):
        if self.flowchart_page.current_branch_state_YN == "No":
            self.merge_branch_action.setVisible(True)
        else:
            self.merge_branch_action.setVisible(False)

    def closeEvent(self, event):
        # Bevor das Fenster zugeht, feuern wir das Signal ab!
        print("Drawing Tool closing, emitting signal...")
        self.editor_closed_signal.emit()
        
        # Standard Schließ-Verhalten
        event.accept()
        
class StartPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

        layout = QVBoxLayout(self)

        label = QLabel("Projection-Based Augmented Reality Assembly Working Station")
        label.setFont(QFont("Arial", 24))  # Kleinere Schrift
        label.setStyleSheet("color: white;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(20)

        main_button = QPushButton("Create Step For Flowchart")
        main_button.setFont(QFont("Arial", 20))
        main_button.setMinimumSize(500, 100)
        main_button.clicked.connect(lambda: self.goto_flowchart_page())

        quit_button = QPushButton("Quit")
        quit_button.setFont(QFont("Arial", 20))
        quit_button.setMinimumSize(300, 100)
        quit_button.clicked.connect(self.close)

        button_layout.addWidget(main_button)
        button_layout.addWidget(quit_button)

        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(label)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def goto_flowchart_page(self):
        self.main_window.stacked_widget.setCurrentIndex(1)  # Switch to FlowchartPage

    def resetToolbars(self):
        self.main_window.tools_toolbar.hide()
        self.main_window.fill_shape_toolbar.hide()
        self.main_window.colors_toolbar.hide()
        self.main_window.save_button_toolbar.hide()

class FlowchartPage(QWidget):
    """
    A page that displays a grid of SVG icons representing different flowchart nodes.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

        self.grid_layout = QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.grid_layout.setSpacing(20)

        self.main_layout = QVBoxLayout(self)
        self.button_layout = QHBoxLayout()

        back_button = QPushButton("Back to Start")
        back_button.clicked.connect(lambda: self.main_window.stacked_widget.setCurrentIndex(0))
        back_button.setFont(QFont("Arial", 20))
        back_button.setMinimumSize(300, 100)

        self.button_layout.addWidget(back_button)
        self.button_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.button_layout.setContentsMargins(0, 0, 200, 100)

        self.main_layout.addLayout(self.grid_layout)
        self.main_layout.addLayout(self.button_layout)
        self.setLayout(self.main_layout)

        self.svg_files = self.get_svg_files()
        self.create_svg_grid()

        self.subroutine_connection_direction = None

        # Initialize flowchart with a Start node as the current node
        st = StartNode("")
        self.main_window.current_flowchart_node = st
        self.start_node = st

        self.flowchart_done = False

        self.current_branch_state_YN = None # To check which branch we are on depending on the condition node (Yes or No Branch)

        self.is_merging = False

        output_dir = Path("legacy/resources/flowchart_dynamic")
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

        self.output_svg_path = Path(f"{output_dir}/current_flowchart.svg")

    def get_svg_files(self):
        svg_dir = Path("legacy/resources/flowchart_icons")

        if not svg_dir.exists():
            svg_dir.mkdir()
            self.create_dummy_svg(svg_dir / "icon1.svg", "red")
            self.create_dummy_svg(svg_dir / "icon2.svg", "blue")
            self.create_dummy_svg(svg_dir / "icon3.svg", "green")
            self.create_dummy_svg(svg_dir / "icon4.svg", "yellow")

        svg_paths = [f for f in svg_dir.glob("*.svg")]

        if len(svg_paths) < 5:
            print("WARNING: Not enough SVGs found, creating dummy SVGs.")

            for i in range(len(svg_paths), 5):
                self.create_dummy_svg(svg_dir / f"icon{i+1}.svg", "gray")
            svg_paths = [f for f in svg_dir.glob("*.svg")]

        return svg_paths[:5]

    def create_dummy_svg(self, path: Path, color):
        svg_content = f"""
        <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            <rect x="0" y="0" width="100" height="100" fill="{color}"/>
            <circle cx="50" cy="50" r="40" fill="white" stroke="{color}" stroke-width="2"/>
            <text x="50" y="60" font-family="Arial" font-size="20" text-anchor="middle" fill="{color}">SVG</text>
        </svg>
        """
        with open(path, "w") as f:
            f.write(svg_content)

    def create_svg_grid(self):
        row = 0
        col = 0
        for i, svg_path in enumerate(self.svg_files):
            # Get the flowchart node name from the SVG filename by removing everything before _
            flowchart_node_name = svg_path.stem.split("_", 1)[0]
            svg_widget = ClickableSvgWidget(str(svg_path), flowchart_node_name)
            svg_widget.clicked.connect(lambda _, w=svg_widget: self.goto_drawing_tool_page(w))
            self.grid_layout.addWidget(svg_widget, row, col)

            col += 1
            if col > 2: # 2 columns (0, 1)
                col = 0
                row += 1

    def goto_drawing_tool_page(self, svg_widget):

        if self.flowchart_done:
            print("Flowchart is already completed. No more nodes can be added.")
            return
        
        match svg_widget.name:
            case "operation":
                popup_op_text = PopupDialog(self, dialog_type="text_input", header="Operation Description")
                result_op = popup_op_text.exec()

                if not self.isPopupResultValid(result_op, popup_op_text):
                    return

                op = OperationNode(popup_op_text.user_input)

                self.connectPreviousToNewNode(previous_node=self.main_window.current_flowchart_node, new_node=op)
                self.main_window.current_flowchart_node = op
                
            case "condition":
                popup_cond_text = PopupDialog(self, dialog_type="text_input", header="Condition Description")
                result = popup_cond_text.exec()

                if not self.isPopupResultValid(result, popup_cond_text):
                    return

                cond = ConditionNode(popup_cond_text.user_input)

                self.connectPreviousToNewNode(previous_node=self.main_window.current_flowchart_node, new_node=cond)
                self.main_window.current_flowchart_node = cond

            case "inputoutput":
                popup_io = PopupDialog(self, dialog_type="buttons", header="Choose Input/Output Type", button_count=2, button_texts=["input", "output"])
                result_io = popup_io.exec()

                if not self.isPopupResultValid(result_io, popup_io):
                    return
                
                popup_io_text = PopupDialog(self, dialog_type="text_input", header=f"{popup_io.user_input.capitalize()} Text")
                result_io_text = popup_io_text.exec()

                if not self.isPopupResultValid(result_io_text, popup_io_text):
                    return

                if popup_io.user_input == "input":
                    io = InputOutputNode(InputOutputNode.INPUT, popup_io_text.user_input)
                elif popup_io.user_input == "output":
                    io = InputOutputNode(InputOutputNode.OUTPUT, popup_io_text.user_input)

                self.connectPreviousToNewNode(previous_node=self.main_window.current_flowchart_node, new_node=io)
                self.main_window.current_flowchart_node = io

            case "subroutine":
                popup_sub_text = PopupDialog(self, dialog_type="text_input", header="Subroutine Description")
                result_sub = popup_sub_text.exec()

                if not self.isPopupResultValid(result_sub, popup_sub_text):
                    return
                    
                sub = SubroutineNode(svg_widget.name)
                self.connectPreviousToNewNode(previous_node=self.main_window.current_flowchart_node, new_node=sub)
                self.main_window.current_flowchart_node = sub

            case "end":
                e = EndNode("")
                
                self.connectPreviousToNewNode(previous_node=self.main_window.current_flowchart_node, new_node=e)
            
        if not isinstance(self.main_window.current_flowchart_node, StartNode):
            svg_widget.playAnimation()
            
            self.updateFlowchart()

        QTimer.singleShot(1000, lambda: self.parent().setCurrentIndex(2))  # 1000ms delay to ensure SVG is loaded
    
    def updateFlowchart(self):
        self.generateFlowchartSVG(self.start_node)

        if not self.output_svg_path.parent.exists():
            print("ERROR: Output directory does not exist. Creating it now.")
            self.output_svg_path.parent.mkdir(parents=True, exist_ok=True)

        self.load_svg(self.output_svg_path)

        self.main_window.dynamic_node_label.setText(self.main_window.current_flowchart_node.node_name)

    def isPopupResultValid(self, result, popup_text):
        if result == QDialog.DialogCode.Rejected or not popup_text.user_input:
            return False
        return True

    def load_svg(self, svg_path):
        abs_path = svg_path.resolve()
        html = f"""
        <html>
          <body style="background-color: #2e3440;">
            <embed src="{abs_path}" type="image/svg+xml" style="width:100%; height:100%"/>
          </body>
        </html>
        """
        self.main_window.drawing_tool.flowchart_widget.setHtml(html, QUrl.fromLocalFile(str(abs_path.parent)))

    def connectPreviousToNewNode(self, previous_node, new_node):
        """
        Connects the previous node to the new node.

        Args:
            previous_node (FlowchartNode): The previous node in the flowchart.
            new_node (FlowchartNode): The new node to connect.
        """
        if isinstance(new_node, (OperationNode, InputOutputNode, SubroutineNode)) and not isinstance(previous_node, EndNode):
            if not isinstance(previous_node, ConditionNode):
                previous_node.connect(new_node)
            else:
                self.connectToConditionNode(previous_node, new_node)
        elif isinstance(new_node, ConditionNode) and not isinstance(previous_node, EndNode):
            if not isinstance(previous_node, ConditionNode):
                # First new branch will be the Yes branch for the first Condition Node that is added
                if self.main_window.current_flowchart_branch == "main" and self.current_branch_state_YN is None:
                    self.current_branch_state_YN = "Yes"

                if self.is_merging: 
                    previous_node.connect(new_node, "right")
                    self.switchToPreviousBranch()
                    self.is_merging = False
                    return

                # To keep the direction of connections consequent
                if self.current_branch_state_YN == "No":
                    previous_node.connect(new_node, "right")
                else:
                    previous_node.connect(new_node, "bottom")
            else:
                self.connectToConditionNode(previous_node, new_node)

            self.addConditionBranch(new_node)
        elif isinstance(new_node, EndNode) and not isinstance(previous_node, StartNode):
            if isinstance(previous_node, ConditionNode):
                self.connectToConditionNode(previous_node, new_node)
            else:
                previous_node.connect(new_node)

            if self.main_window.current_flowchart_branch == "main":
                self.flowchart_done = True
                print("Flowchart is done!") # TODO: Get back to the Projection page and disable to press the capture photo button by messaging the user that the flowchart is already done (He can only save the manual now)!
            else:
                self.switchToPreviousBranch()

    def switchToPreviousBranch(self):
        current_branch = self.main_window.current_flowchart_branch
        current_branch_index = self.main_window.branches_order.index(current_branch)
        self.main_window.branches_dict[current_branch] = "Completed"

        # We iterate backwards through the branches to find the one that's not completed yet and switch to that
        for branch in self.main_window.branches_order[current_branch_index - 1::-1]:
            if self.main_window.branches_dict[branch] == "Completed":
                continue
            else:
                self.main_window.current_flowchart_node = self.main_window.condition_nodes_to_branches[branch][-1]
                self.main_window.current_flowchart_branch = branch
                break
                
        self.main_window.dynamic_branch_label.setText(self.main_window.current_flowchart_branch)

        self.switchBranchStateYN()
        print("Current YN Branch: ", self.current_branch_state_YN)

        print("Switched back to previous branch:", self.main_window.current_flowchart_branch)

    def connectToConditionNode(self, condition_node, new_node):
        if self.current_branch_state_YN == "Yes":
            condition_node.connect_yes(new_node)
        else:
            condition_node.connect_no(new_node)

            if self.is_merging:
                self.is_merging = False

    def addConditionBranch(self, condition_node):
        self.main_window.condition_nodes_to_branches[self.main_window.current_flowchart_branch].append(condition_node)
        self.main_window.branch_counter += 1

        self.switchBranchStateYN()

        new_branch = f"branch_{self.main_window.branch_counter - 1}_{condition_node.node_name} ({self.current_branch_state_YN})"
        self.main_window.branches_dict[new_branch] = "Active"
        self.main_window.branches_order.append(new_branch)

        self.main_window.current_flowchart_branch = new_branch
        self.main_window.condition_nodes_to_branches.setdefault(new_branch, []).append(condition_node)

        self.main_window.dynamic_branch_label.setText(self.main_window.current_flowchart_branch)

        print("Branches after adding condition branch:", self.main_window.branches_dict)
        for branch, condition_nodes in self.main_window.condition_nodes_to_branches.items():
            print(f"Branch '{branch}': {[node.node_name for node in condition_nodes]}")
        print("Current Branch:", self.main_window.current_flowchart_branch)

    def mergeWithPreviousBranch(self):
        self.is_merging = True
        
        current_branch = self.main_window.current_flowchart_branch
        if self.current_branch_state_YN == "Yes" or current_branch == "main" or self.main_window.branches_dict[current_branch] == "Completed":
            print("No Merge possible!")
            return

        yes_branches = self.getYesBranches()
        yes_branches_count = len(yes_branches)
        print("Length Yes Branches: ", yes_branches_count)

        button_texts = set()
        for branch in yes_branches:
            for cond in self.main_window.condition_nodes_to_branches[branch]:
                button_texts.add(cond.node_text)
        print("Length Button Texts: ", len(button_texts))

        popup_merge = PopupDialog(self, dialog_type="buttons", header="To which Condition Node do you want to connect to? (Branches will be merged)", button_count=yes_branches_count, button_texts=list(button_texts))
        result_merge = popup_merge.exec()

        if not self.isPopupResultValid(result_merge, popup_merge):
            return

        condition_text = popup_merge.user_input

        target_condition_node = None

        for cond_list in self.main_window.condition_nodes_to_branches.values():
            for cond in cond_list:
                if cond.node_text == condition_text:
                    target_condition_node = cond
                    break

        if target_condition_node is None:
            print("ERROR: No condition node found for that description!")
            return

        current_node = self.main_window.current_flowchart_node

        self.connectPreviousToNewNode(previous_node=current_node, new_node=target_condition_node)

        self.main_window.toggleMergeButton()

        self.updateFlowchart()

    def getYesBranches(self):
        yes_branches = [
            branch for branch in self.main_window.branches_order 
            if "(Yes)" in branch or branch == "main"
        ]
        return yes_branches

    def switchBranchStateYN(self):
        if self.current_branch_state_YN == "Yes":
            self.current_branch_state_YN = "No"
        else:
            self.current_branch_state_YN = "Yes"

    def generateFlowchartSVG(self, start_node):
        fc = Flowchart(start_node)
        flowchart_dsl = fc.flowchart()
        print("Flowchart DSL generated: \n----------------------------------------------------------------------")
        print(flowchart_dsl)
        print("----------------------------------------------------------------------")

        temp_dsl_file = None    
        try:
            # 2. Write DSL to a temporary file with LF line endings (LF is important for compatibility with the diagrams tool because Windows uses CRLF by default!!!)
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".flowchart", encoding="utf-8", newline='\n') as temp_dsl_file:
                temp_dsl_file.write(flowchart_dsl)
                temp_dsl_path = Path(temp_dsl_file.name) # Use Path object
            print(f"Step 2: Flowchart DSL saved to temporary file: {temp_dsl_path} \n")

            # 3. Call `seflless/diagrams` CLI tool
            print(f"Step 3: Converting DSL to SVG with '{self.main_window.diagrams_tool_path} flowchart' CLI tool... \n")
            command = [
                self.main_window.diagrams_tool_path, # Dynamically found path
                "flowchart",
                str(temp_dsl_path), # Convert Path to string for the command
                str(self.output_svg_path)    # Convert Path to string for the command
            ]
            
            subprocess.run(command, check=True, capture_output=True, text=True)

            print(f"Command executed: {' '.join(command)}")

            print(f"Step 4: SVG file successfully created at: {self.output_svg_path} \n")

        except subprocess.CalledProcessError as e:
            print(f"Error executing the '{self.main_window.diagrams_tool_path}' tool:")
            print(f"Return code: {e.returncode}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            print("Possible reason: The provided DSL is faulty or the tool could not read/write the files.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            # Use Path object for file operations
            if temp_dsl_path.exists():
                temp_dsl_path.unlink()
                print(f"Temporary DSL file deleted: {temp_dsl_path}")

    def resetToolbars(self):
        self.main_window.tools_toolbar.hide()
        self.main_window.fill_shape_toolbar.hide()
        self.main_window.colors_toolbar.hide()
        self.main_window.save_button_toolbar.hide()

class ClickableSvgWidget(QWidget):
    clicked = pyqtSignal(str)

    def __init__(self, svg_path, name, parent=None):
        super().__init__(parent)
        self.svg_path = svg_path
        self.renderer = QSvgRenderer(svg_path)
        self.renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.setMinimumSize(400, 400)  # Flexible Größe mit Minimum
        self.setMaximumSize(600, 600)  # Flexible Größe mit Maximum
        self.name = name
        self.condition_node_decision = None  # Store the decision for condition nodes

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
            self.clicked.emit(self.svg_path)
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

class PopupDialog(QDialog):
    def __init__(self, parent=None, header="", dialog_type="buttons", button_count=0, button_texts=[], placeholder_text=""):
        super().__init__(parent)
        self.user_input = None
        self.dialog_type = dialog_type

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        # Dynamic sizing based on content
        base_height = 200  # Base height for header and padding
        if dialog_type == "text_input":
            content_height = base_height + 120  # Extra space for text input
        else:
            button_height = 80
            spacing_per_button = 15
            content_height = base_height + (button_count * button_height) + (button_count * spacing_per_button)
        
        self.setMinimumSize(400, content_height)
        self.resize(500, content_height)  # Set initial size instead of maximum

        shadow_widget = QWidget(self)
        shadow_widget.setObjectName("shadow_widget")

        shadow_widget.setGeometry(10, 10, self.width() - 20, self.height() - 20)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow_widget.setGraphicsEffect(shadow)

        layout = QVBoxLayout(shadow_widget)
        layout.setContentsMargins(30, 30, 30, 30) 
        layout.setSpacing(20)

        # Titel
        title = QLabel(header)
        font_title = QFont()
        font_title.setPointSize(20)
        title.setFont(font_title)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white;")
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
            button_layout.setSpacing(15)  # Abstand zwischen OK und Cancel
            
            ok_button = QPushButton("OK")
            ok_button.setFont(QFont("Arial", 18))
            ok_button.setMinimumHeight(60)
            ok_button.clicked.connect(self.on_text_input_ok)
            
            cancel_button = QPushButton("Cancel")
            cancel_button.setFont(QFont("Arial", 18))
            cancel_button.setMinimumHeight(60)
            cancel_button.clicked.connect(self.reject)
            
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)

            self.text_input.setFocus()

        else:
            # Buttons
            font_btn = QFont()
            font_btn.setPointSize(24)

            for i in range(button_count):
                if i < len(button_texts):
                    button = QPushButton(button_texts[i])
                    button.setFont(font_btn)
                    button.setMinimumHeight(80)
                    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                    layout.addWidget(button)

                    button.clicked.connect(lambda _, btn=button: self.on_choice(btn.text()))
                    
                    if i < button_count - 1:  # Don't add spacing after the last button
                        layout.addSpacing(15)

        # Adjust the shadow widget size after layout is complete
        QTimer.singleShot(0, self.adjust_size)

    def adjust_size(self):
        """Adjust the dialog and shadow widget size after layout is complete."""
        self.adjustSize()
        shadow_widget = self.findChild(QWidget, "shadow_widget")
        if shadow_widget:
            shadow_widget.setGeometry(10, 10, self.width() - 20, self.height() - 20)

    def on_choice(self, choice_text):
        self.user_input = choice_text
        self.accept()

    def on_text_input_ok(self):
        if hasattr(self, 'text_input'):
            self.user_input = self.text_input.text().strip()
            if self.user_input:
                self.accept()

    def reject(self):
        if self.dialog_type == "text_input":
            super().reject()


if __name__ == '__main__':
    # Set environment variable to control DPI awareness
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
    os.environ["QT_SCALE_FACTOR"] = "1"
    
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to the input image")
    ap.add_argument("--output-dir", required=True, help="Target folder for output")
    args = ap.parse_args()

    # Disable High DPI scaling to prevent automatic scaling issues
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    wnd = MainWindow(args.input, args.output_dir)
    wnd.show()
    sys.exit(app.exec())