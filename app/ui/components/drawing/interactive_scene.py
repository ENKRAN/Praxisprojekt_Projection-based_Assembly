import math
from PyQt6.QtWidgets import (
    QGraphicsScene, 
    QGraphicsPathItem, 
    QGraphicsTextItem, 
    QGraphicsRectItem, 
    QGraphicsEllipseItem, 
    QGraphicsItem
)
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainterPath, QPen, QColor, QBrush, QTransform, QFont

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