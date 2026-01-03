# RZMenu/qt_editor/widgets/area.py
"""
RZAreaWidget - A container widget that allows dynamic panel type switching.
Similar to Blender's area system where each area can display any editor type.
"""
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.widgets import RZPanelWidget
from .lib.theme import get_current_theme
from .panel_base import RZEditorPanel
from .panel_factory import PanelFactory


class RZAreaHeader(QtWidgets.QFrame):
    """
    Header bar for RZAreaWidget containing the panel type selector.
    """
    panel_type_changed = QtCore.Signal(str)  # Emits new panel_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RZAreaHeader")
        self.setFixedHeight(24)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        
        # Panel type selector
        self.combo_type = QtWidgets.QComboBox()
        self.combo_type.setObjectName("AreaTypeSelector")
        self.combo_type.setMinimumWidth(100)
        self.combo_type.setMaximumWidth(150)
        self._populate_panel_types()
        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self.combo_type)
        
        layout.addStretch()
        
        self.apply_theme()
    
    def _populate_panel_types(self):
        """Populate combo box with available panel types."""
        self.combo_type.blockSignals(True)
        self.combo_type.clear()
        
        panels = PanelFactory.get_available_panels()
        for panel_info in panels:
            self.combo_type.addItem(
                panel_info["name"],
                userData=panel_info["id"]
            )
        
        self.combo_type.blockSignals(False)
    
    def _on_type_changed(self, index: int):
        """Handle combo box selection change."""
        if index < 0:
            return
        panel_id = self.combo_type.itemData(index)
        if panel_id:
            self.panel_type_changed.emit(panel_id)
    
    def set_current_type(self, panel_id: str):
        """Set the combo box to show the specified panel type."""
        self.combo_type.blockSignals(True)
        for i in range(self.combo_type.count()):
            if self.combo_type.itemData(i) == panel_id:
                self.combo_type.setCurrentIndex(i)
                break
        self.combo_type.blockSignals(False)
    
    def get_current_type(self) -> str:
        """Get the currently selected panel type ID."""
        return self.combo_type.currentData() or ""
    
    def apply_theme(self):
        """Apply theme styling to the header."""
        theme = get_current_theme()
        self.setStyleSheet(f"""
            #RZAreaHeader {{
                background-color: {theme.get('bg_header', '#3A404A')};
                border: none;
                border-bottom: 1px solid {theme.get('border_main', '#2A2E35')};
            }}
            #AreaTypeSelector {{
                background-color: {theme.get('bg_input', '#252930')};
                color: {theme.get('text_main', '#E0E2E4')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 2px;
                padding: 2px 4px;
                font-size: 11px;
            }}
            #AreaTypeSelector:hover {{
                border-color: {theme.get('accent', '#5298D4')};
            }}
            #AreaTypeSelector::drop-down {{
                border: none;
                width: 16px;
            }}
        """)


class RZAreaWidget(RZPanelWidget):
    """
    Container widget that hosts an RZEditorPanel with a header for type switching.
    
    Usage:
        area = RZAreaWidget()
        area.set_panel_type("OUTLINER")
        
        # Get the current panel instance
        panel = area.get_current_panel()
    """
    
    # Signal emitted when the panel type changes
    panel_changed = QtCore.Signal(str, object)  # (panel_id, panel_instance)
    
    def __init__(self, initial_panel_id: str = None, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("RZAreaWidget")
        
        self._current_panel: RZEditorPanel = None
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        self.header = RZAreaHeader(self)
        self.header.panel_type_changed.connect(self.change_panel)
        main_layout.addWidget(self.header)
        
        # Content container
        self.content_container = QtWidgets.QWidget()
        self.content_container.setObjectName("RZAreaContent")
        self.content_layout = QtWidgets.QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        main_layout.addWidget(self.content_container, stretch=1)
        
        # Initialize with panel if provided
        if initial_panel_id:
            self.set_panel_type(initial_panel_id)
        
        self.apply_theme()
    
    def set_panel_type(self, panel_id: str):
        """
        Set the panel type, creating the panel if needed.
        This is the initial setup method - use change_panel for runtime changes.
        """
        if self._current_panel and self._current_panel.PANEL_ID == panel_id:
            return  # Already showing this panel type
        
        self.change_panel(panel_id)
        self.header.set_current_type(panel_id)
    
    def change_panel(self, panel_id: str):
        """
        Switch to a different panel type.
        Removes the current panel and creates a new one.
        """
        # Remove current panel if exists
        if self._current_panel:
            self._current_panel.on_deactivate()
            self.content_layout.removeWidget(self._current_panel)
            self._current_panel.deleteLater()
            self._current_panel = None
        
        # Create new panel
        try:
            self._current_panel = PanelFactory.create_panel(panel_id, parent=self.content_container)
            if self._current_panel:
                self.content_layout.addWidget(self._current_panel)
                self._current_panel.on_activate()
                self.panel_changed.emit(panel_id, self._current_panel)
        except KeyError as e:
            # Panel type not registered
            print(f"[RZAreaWidget] Failed to create panel: {e}")
            self._create_placeholder(panel_id)
    
    def _create_placeholder(self, panel_id: str):
        """Create a placeholder widget when panel creation fails."""
        placeholder = QtWidgets.QLabel(f"Panel '{panel_id}' not available")
        placeholder.setAlignment(QtCore.Qt.AlignCenter)
        placeholder.setStyleSheet("color: #888; font-style: italic;")
        self.content_layout.addWidget(placeholder)
    
    def get_current_panel(self) -> RZEditorPanel:
        """
        Get the current panel instance.
        
        Returns:
            The current RZEditorPanel instance, or None if no panel is set.
        """
        return self._current_panel
    
    def get_current_panel_id(self) -> str:
        """Get the ID of the currently displayed panel type."""
        if self._current_panel:
            return self._current_panel.PANEL_ID
        return ""
    
    def apply_theme(self):
        """Apply theme styling."""
        theme = get_current_theme()
        self.setStyleSheet(f"""
            #RZAreaWidget {{
                background-color: {theme.get('bg_panel', '#2C313A')};
                border: 1px solid {theme.get('border_main', '#3A404A')};
                border-radius: 4px;
            }}
            #RZAreaContent {{
                background-color: transparent;
            }}
        """)
        
        if hasattr(self, 'header'):
            self.header.apply_theme()
    
    def update_theme_styles(self):
        """Update theme for area and current panel."""
        self.apply_theme()
        if self._current_panel and hasattr(self._current_panel, 'update_theme_styles'):
            self._current_panel.update_theme_styles()

