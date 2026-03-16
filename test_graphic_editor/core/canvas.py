from PySide6.QtGui import QPainter, QTabletEvent, QMouseEvent, QImage, QPainterPath
from core.document import Document
from core.brush_tool import BrushTool

class VectorCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Document & Tools
        self.doc = Document()
        self.brush = BrushTool()
        self.last_pos = QPointF(0, 0)
        
        # Performance settings
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
        # Initial image for testing raster drawing
        self._init_canvas()

    def _init_canvas(self):
        # Create a base raster layer if none exists or for testing
        layer = self.doc.get_active_layer()
        if not layer.raster_data:
            layer.raster_data = QImage(self.doc.width, self.doc.height, QImage.Format_ARGB32_Premultiplied)
            layer.raster_data.fill(Qt.transparent)
        
        self.scene.clear()
        self.raster_item = self.scene.addPixmap(Qt.NoPen) # We'll update this
        self._update_scene()

    def _update_scene(self):
        """Redraw document layers to scene."""
        layer = self.doc.get_active_layer()
        if layer and layer.raster_data:
            from PySide6.QtGui import QPixmap
            self.raster_item.setPixmap(QPixmap.fromImage(layer.raster_data))

    def tabletEvent(self, event: QTabletEvent):
        """Handle graphics tablet events."""
        pos = self.mapToScene(event.position().toPoint())
        pressure = event.pressure()
        
        if event.type() == QTabletEvent.TabletPress:
            self.last_pos = pos
        elif event.type() == QTabletEvent.TabletMove:
            self._draw(self.last_pos, pos, pressure)
            self.last_pos = pos
            
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        self.last_pos = self.mapToScene(event.position().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton:
            pos = self.mapToScene(event.position().toPoint())
            self._draw(self.last_pos, pos, 1.0)
            self.last_pos = pos
        super().mouseMoveEvent(event)

    def _draw(self, start, end, pressure):
        layer = self.doc.get_active_layer()
        if layer and layer.raster_data:
            self.brush.paint_stroke(layer.raster_data, start, end, pressure)
            self._update_scene()

    def wheelEvent(self, event):
        """Handle zooming."""
        if event.modifiers() == Qt.ControlModifier:
            zoom_in_factor = 1.25
            zoom_out_factor = 1 / zoom_in_factor
            if event.angleDelta().y() > 0:
                self.scale(zoom_in_factor, zoom_in_factor)
            else:
                self.scale(zoom_out_factor, zoom_out_factor)
        else:
            super().wheelEvent(event)
