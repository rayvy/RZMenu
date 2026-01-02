# RZMenu/qt_editor/core/signals.py
from PySide6.QtCore import QObject, Signal

class RZSignalManager(QObject):
    structure_changed = Signal()  # List changed (Outliner)
    transform_changed = Signal()  # Pos/Size changed (Viewport)
    data_changed = Signal()       # Props changed (Inspector)
    selection_changed = Signal()  # Selection changed
    
    # Context/Hover Area changed
    context_updated = Signal()

    # NEW: Config/Theme changed
    # Отправляет ключ изменившейся секции (например, "appearance")
    config_changed = Signal(str) 
    theme_changed_signal = Signal() # Explicit signal for theme editor updates

SIGNALS = RZSignalManager()
IS_UPDATING_FROM_QT = False