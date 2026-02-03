from PyQt6.QtWidgets import QGraphicsView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter

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