# RZMenu/qt_editor/signals.py
from PySide6.QtCore import QObject, Signal

class RZSignalManager(QObject):
    structure_changed = Signal()  # List changed (Outliner)
    transform_changed = Signal()  # Pos/Size changed (Viewport)
    data_changed = Signal()       # Props changed (Inspector)
    selection_changed = Signal()  # Selection changed
    
    # NEW: Context/Hover Area changed (для мгновенного обновления футера)
    context_updated = Signal()

SIGNALS = RZSignalManager()
IS_UPDATING_FROM_QT = False