# RZMenu/qt_editor/widgets/panel_base.py
"""
Base class for all editor panels in the RZMenu Editor.
Provides a unified interface for the docking system.

Panels are AUTONOMOUS - they subscribe to core.SIGNALS upon activation
and unsubscribe upon deactivation. This prevents RuntimeError when panels
are destroyed during area type switching.
"""
from PySide6 import QtCore, QtWidgets
from .lib.widgets import RZPanelWidget


class RZEditorPanel(RZPanelWidget):
    """
    Abstract base class for all editor panels.
    
    Subclasses MUST define:
        - PANEL_ID: str - Unique identifier for the panel type (e.g., "OUTLINER")
        - PANEL_NAME: str - Human-readable name (e.g., "Outliner")
        - PANEL_ICON: str - Icon identifier for the panel
    
    Subclasses SHOULD override:
        - _connect_signals(): Connect to core.SIGNALS for data updates
        - _disconnect_signals(): Disconnect from core.SIGNALS
        - refresh_data(): Called on activation and when data changes
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
        self._signals_connected = False
        
        # Ensure panel expands to fill available space
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
    
    def on_activate(self):
        """
        Called when this panel is created or becomes active.
        Connects to global signals and performs initial data refresh.
        
        Subclasses should call super().on_activate() AFTER their setup.
        """
        self._is_panel_active = True
        if not self._signals_connected:
            self._connect_signals()
            self._signals_connected = True
        self.panel_focus_changed.emit(True)
        # Perform initial data load
        self.refresh_data()
    
    def on_deactivate(self):
        """
        Called when this panel is about to be destroyed or deactivated.
        Disconnects from global signals to prevent calls to deleted objects.
        
        Subclasses should call super().on_deactivate() FIRST.
        """
        self._is_panel_active = False
        if self._signals_connected:
            self._disconnect_signals()
            self._signals_connected = False
        self.panel_focus_changed.emit(False)
    
    def _connect_signals(self):
        """
        Connect to core.SIGNALS for data updates.
        Override in subclasses to connect to relevant signals.
        
        Example:
            from ...core.signals import SIGNALS
            SIGNALS.structure_changed.connect(self.refresh_data)
        """
        pass
    
    def _disconnect_signals(self):
        """
        Disconnect from core.SIGNALS.
        Override in subclasses. Use try-except for safety.
        
        Example:
            from ...core.signals import SIGNALS
            try:
                SIGNALS.structure_changed.disconnect(self.refresh_data)
            except (RuntimeError, TypeError):
                pass
        """
        pass
    
    def refresh_data(self):
        """
        Fetch and display current data from core.
        Override in subclasses to implement panel-specific data loading.
        
        This is called:
        - On panel activation
        - When relevant signals are emitted
        """
        pass
    
    def get_action_manager(self):
        """
        Find the RZActionManager by traversing up to the main window.
        Returns None if not found.
        """
        widget = self
        while widget:
            parent = widget.parent()
            if parent is None:
                # We've reached a top-level widget
                if hasattr(widget, 'action_manager'):
                    return widget.action_manager
                break
            # Check if parent has action_manager
            if hasattr(parent, 'action_manager'):
                return parent.action_manager
            widget = parent
        
        # Fallback: try window() method
        try:
            win = self.window()
            if win and hasattr(win, 'action_manager'):
                return win.action_manager
        except:
            pass
        
        return None
    
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
