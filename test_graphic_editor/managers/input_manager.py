from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QTabletEvent, QMouseEvent

class InputManager(QObject):
    """Routes input events from the canvas to the appropriate tool or operator."""
    stroke_updated = Signal(dict) # Data containing pressure, pos, etc.

    def __init__(self, context_manager):
        super().__init__()
        self.context = context_manager

    def handle_tablet(self, event: QTabletEvent):
        data = {
            "pos": event.position(),
            "pressure": event.pressure(),
            "tilt": event.xTilt(), # -60 to 60 usually
            "type": event.type()
        }
        self.stroke_updated.emit(data)
        # Here we would call the active tool's logic

    def handle_mouse(self, event: QMouseEvent):
        data = {
            "pos": event.position(),
            "pressure": 1.0, # Default pressure for mouse
            "type": event.type()
        }
        self.stroke_updated.emit(data)
