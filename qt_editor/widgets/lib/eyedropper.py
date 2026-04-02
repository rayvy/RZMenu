# RZMenu/qt_editor/widgets/lib/eyedropper.py
from PySide6 import QtWidgets, QtCore, QtGui

class RZEyedropperOverlay(QtWidgets.QWidget):
    """
    Full-screen overlay for global color picking.
    Captures the primary screen at instantiation.
    """
    colorPicked = QtCore.Signal(QtGui.QColor)
    cancelled = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setCursor(QtCore.Qt.CrossCursor)
        self.setMouseTracking(True)
        
        # Capture screen
        screen = QtWidgets.QApplication.primaryScreen()
        self._pixmap = screen.grabWindow(0)
        self._image = self._pixmap.toImage()
        
        self.setGeometry(screen.geometry())
        self._current_color = QtGui.QColor(0, 0, 0)
        self._mouse_pos = QtCore.QPoint(0, 0)
        
        # Loupe constants
        self.LOUPE_SIZE = 120
        self.ZOOM = 8

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.cancelled.emit()
            self.close()
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        self._mouse_pos = event.pos()
        if 0 <= self._mouse_pos.x() < self._image.width() and 0 <= self._mouse_pos.y() < self._image.height():
            self._current_color = self._image.pixelColor(self._mouse_pos)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.colorPicked.emit(self._current_color)
            self.close()
        elif event.button() == QtCore.Qt.RightButton:
            self.cancelled.emit()
            self.close()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Draw the captured screen (dimmed)
        painter.drawPixmap(0, 0, self._pixmap)
        
        # Dimming effect (optional, maybe just for the magnifying part?)
        # Let's not dim the whole thing, just show a clear loupe.
        
        # Loupe (Magnifier)
        lx, ly = self._mouse_pos.x(), self._mouse_pos.y()
        r = self.LOUPE_SIZE / 2
        
        # Draw Loupe Circle
        loupe_rect = QtCore.QRect(lx - r, ly - r, self.LOUPE_SIZE, self.LOUPE_SIZE)
        
        # Capture zoomed content
        src_size = self.LOUPE_SIZE / self.ZOOM
        src_rect = QtCore.QRect(lx - src_size/2, ly - src_size/2, src_size, src_size)
        
        painter.save()
        path = QtGui.QPainterPath()
        path.addEllipse(loupe_rect)
        painter.setClipPath(path)
        
        # Draw zoomed pixmap
        painter.drawPixmap(loupe_rect, self._pixmap, src_rect)
        
        painter.restore()
        
        # Loupe Border
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
        painter.drawEllipse(loupe_rect)
        
        # Crosshair in center
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 100), 1))
        painter.drawLine(lx - 10, ly, lx + 10, ly)
        painter.drawLine(lx, ly - 10, lx, ly + 10)
        
        # Show Color Info
        hex_text = self._current_color.name().upper()
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 0, 0, 150))
        painter.drawRect(lx - 30, ly + r + 5, 60, 20)
        
        painter.setPen(QtGui.QColor(255, 255, 255))
        painter.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold))
        painter.drawText(QtCore.QRect(lx - 30, ly + r + 5, 60, 20), QtCore.Qt.AlignCenter, hex_text)

def start_eyedropper(callback):
    """Utility to launch the eyedropper and return color to a callback."""
    overlay = RZEyedropperOverlay()
    overlay.colorPicked.connect(callback)
    overlay.showFullScreen()
    # Keep reference so it doesn't get garbage collected
    overlay._ref = overlay 
    return overlay
