# RZMenu/qt_editor/signals.py
from PySide6.QtCore import QObject, Signal

class RZSignalManager(QObject):
    structure_changed = Signal()  # List changed (Outliner)
    transform_changed = Signal()  # Pos/Size changed (Viewport)
    data_changed = Signal()       # Props changed (Inspector)
    selection_changed = Signal()  # Selection changed

# Global Instance
SIGNALS = RZSignalManager()

# Global Flag to prevent infinite loops (Blender -> Qt -> Blender)
IS_UPDATING_FROM_QT = False