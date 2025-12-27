#RZMenu/qt_editor/widgets/viewport.py
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtCore import Qt

class Viewport(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setBackgroundBrush(QBrush(QColor("#181818")))

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        
        # Set grid color and pen
        grid_color = QColor("#2a2a2a")
        pen = QPen(grid_color, 1, Qt.SolidLine)
        painter.setPen(pen)

        # Draw grid lines
        left = int(rect.left())
        right = int(rect.right())
        top = int(rect.top())
        bottom = int(rect.bottom())
        
        grid_size = 20
        
        # Draw vertical lines
        first_left = left - (left % grid_size)
        for x in range(first_left, right, grid_size):
            painter.drawLine(x, top, x, bottom)
            
        # Draw horizontal lines
        first_top = top - (top % grid_size)
        for y in range(first_top, bottom, grid_size):
            painter.drawLine(left, y, right, y)