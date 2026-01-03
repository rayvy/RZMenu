# RZMenu/qt_editor/widgets/panel_base.py
"""
Base class for all editor panels in the RZMenu Editor.
Provides a unified interface for the docking system.
"""
from PySide6 import QtCore
from .lib.widgets import RZPanelWidget


class RZEditorPanel(RZPanelWidget):
    """
    Abstract base class for all editor panels.
    
    Subclasses MUST define:
        - PANEL_ID: str - Unique identifier for the panel type (e.g., "OUTLINER")
        - PANEL_NAME: str - Human-readable name (e.g., "Outliner")
        - PANEL_ICON: str - Icon identifier for the panel
    """
    
    # Class-level panel metadata (override in subclasses)
    PANEL_ID: str = "UNDEFINED"
    PANEL_NAME: str = "Undefined Panel"
    PANEL_ICON: str = "file"
    
    # Signal emitted when panel gains/loses focus (optional use)
    panel_focus_changed = QtCore.Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._is_panel_active = False
    
    def on_activate(self):
        """
        Called when this panel becomes the active/focused panel.
        Override in subclasses to implement custom activation behavior.
        """
        self._is_panel_active = True
        self.panel_focus_changed.emit(True)
    
    def on_deactivate(self):
        """
        Called when this panel loses focus/is deactivated.
        Override in subclasses to implement custom deactivation behavior.
        """
        self._is_panel_active = False
        self.panel_focus_changed.emit(False)
    
    @property
    def is_panel_active(self) -> bool:
        """Returns whether this panel is currently the active panel."""
        return self._is_panel_active
    
    @classmethod
    def get_panel_info(cls) -> dict:
        """Returns metadata about this panel type."""
        return {
            "id": cls.PANEL_ID,
            "name": cls.PANEL_NAME,
            "icon": cls.PANEL_ICON,
        }

