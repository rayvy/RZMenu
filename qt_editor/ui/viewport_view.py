# RZMenu/qt_editor/ui/viewport_view.py
from PySide6 import QtWidgets, QtCore, QtGui

class ViewportScene(QtWidgets.QGraphicsScene):
    """A custom scene to handle background drawing."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid_size = 20
        
    def drawBackground(self, painter: QtGui.QPainter, rect: QtCore.QRectF):
        # Fill with dark color
        painter.fillRect(rect, QtGui.QColor(45, 45, 45))
        
        # Draw grid lines
        left = int(rect.left()) - (int(rect.left()) % self.grid_size)
        top = int(rect.top()) - (int(rect.top()) % self.grid_size)
        
        lines = []
        # Vertical lines
        x = left
        while x < rect.right():
            lines.append(QtCore.QLineF(x, rect.top(), x, rect.bottom()))
            x += self.grid_size
        
        # Horizontal lines
        y = top
        while y < rect.bottom():
            lines.append(QtCore.QLineF(rect.left(), y, rect.right(), y))
            y += self.grid_size
            
        pen = QtGui.QPen(QtGui.QColor(55, 55, 55), 1)
        painter.setPen(pen)
        painter.drawLines(lines)


class ViewportView(QtWidgets.QGraphicsView):
    """
    The main viewport panel for displaying and interacting with RZElements.
    Handles zooming and panning. The actual items are managed by a presenter.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setScene(ViewportScene(self))
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        
        self._is_panning = False
        self._pan_start_pos = QtCore.QPoint()

    def wheelEvent(self, event: QtGui.QWheelEvent):
        """Zooms the view."""
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """Starts panning or rubber-band selection."""
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        
        super().mousePressEvent(event)
        
        # If not clicking on an item, start rubber band drag
        item = self.itemAt(event.pos())
        if not item:
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.RubberBandDrag)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """Pans the view."""
        if self._is_panning:
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        """Stops panning or rubber-band selection."""
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self._is_panning = False
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            event.accept()
            return
            
        if self.dragMode() == QtWidgets.QGraphicsView.DragMode.RubberBandDrag:
            # Logic to handle selection change will be in the presenter,
            # which listens to the scene's selectionChanged signal.
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)

        super().mouseReleaseEvent(event)
