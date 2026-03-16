from enum import Enum, auto
from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import Qt, QPointF

class LayerType(Enum):
    VECTOR = auto()
    RASTER = auto()
    ADJUSTMENT = auto()
    GROUP = auto()

class Layer:
    def __init__(self, name="New Layer", layer_type=LayerType.VECTOR):
        self.name = name
        self.type = layer_type
        self.visible = True
        self.locked = False
        self.opacity = 1.0 # 0.0 to 1.0
        self.blend_mode = "Normal"
        
        # Data storage
        self.vector_items = [] # List of QGraphicsItem or custom vector objects
        self.raster_data = None # QImage for raster layers
        
    def __str__(self):
        return f"Layer({self.name}, visible={self.visible})"

    def toggle_visibility(self):
        self.visible = not self.visible

    def set_opacity(self, opacity):
        self.opacity = max(0.0, min(1.0, opacity))
