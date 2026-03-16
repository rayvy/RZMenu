from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QRadialGradient, QImage
from PySide6.QtCore import Qt, QPointF

class BrushTool:
    def __init__(self):
        self.size = 20.0
        self.hardness = 0.5 # 0.0 (soft) to 1.0 (hard)
        self.color = QColor(Qt.black)
        self.is_eraser = False

    def paint_stroke(self, image: QImage, last_pos: QPointF, current_pos: QPointF, pressure: float):
        """Draw a series of circles between two points to form a smooth line."""
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Adjust size by pressure
        effective_size = self.size * pressure
        if effective_size <= 0:
            effective_size = 1.0
            
        if self.is_eraser:
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
        
        # Simplified: Draw incremental circles for smooth stroke
        dist = (current_pos - last_pos).manhattanLength()
        steps = max(1, int(dist / (effective_size * 0.1))) # 10% spacing for smoothness
        
        for i in range(steps + 1):
            t = i / steps
            pos = last_pos * (1 - t) + current_pos * t
            self._draw_brush_tip(painter, pos, effective_size)
            
        painter.end()

    def _draw_brush_tip(self, painter, pos, size):
        """Draw a single brush 'stamp' with hardness-based gradient."""
        radius = size / 2.0
        
        if self.hardness >= 0.95:
            # Hard brush: solid circle
            painter.setBrush(QBrush(self.color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(pos, radius, radius)
        else:
            # Soft brush: radial gradient
            gradient = QRadialGradient(pos, radius)
            # Hardness controls where the solid color begins
            stop_pos = max(0.01, self.hardness)
            gradient.setColorAt(0, self.color)
            
            # Fade out to transparent
            fade_color = QColor(self.color)
            fade_color.setAlpha(0)
            gradient.setColorAt(1, fade_color)
            
            # Note: For even better 'hardness' we'd add intermediate stops
            # but this is a good start for standard brush feel.
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(pos, radius, radius)
