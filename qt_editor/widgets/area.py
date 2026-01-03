# RZMenu/qt_editor/widgets/area.py
"""
RZAreaWidget - A container widget that allows dynamic panel type switching.
Similar to Blender's area system where each area can display any editor type.
Supports splitting and closing areas dynamically.
"""
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.widgets import RZPanelWidget
from .lib.theme import get_current_theme
from .panel_base import RZEditorPanel
from .panel_factory import PanelFactory


class RZAreaHeader(QtWidgets.QFrame):
    """
    Header bar for RZAreaWidget containing the panel type selector and area menu.
    """
    panel_type_changed = QtCore.Signal(str)  # Emits new panel_id
    split_vertical_requested = QtCore.Signal()
    split_horizontal_requested = QtCore.Signal()
    close_requested = QtCore.Signal()
    
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
        
        # Area menu button
        self.btn_menu = QtWidgets.QPushButton("☰")
        self.btn_menu.setObjectName("AreaMenuButton")
        self.btn_menu.setFixedSize(20, 18)
        self.btn_menu.setToolTip("Area Options")
        self.btn_menu.clicked.connect(self._show_area_menu)
        layout.addWidget(self.btn_menu)
        
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
    
    def _show_area_menu(self):
        """Show the area options menu."""
        menu = QtWidgets.QMenu(self)
        
        # Split actions
        act_split_v = menu.addAction("⬍ Split Vertical")
        act_split_v.triggered.connect(self.split_vertical_requested.emit)
        
        act_split_h = menu.addAction("⬌ Split Horizontal")
        act_split_h.triggered.connect(self.split_horizontal_requested.emit)
        
        menu.addSeparator()
        
        # Close action
        act_close = menu.addAction("✕ Close Area")
        act_close.triggered.connect(self.close_requested.emit)
        
        # Show menu at button position
        menu.exec(self.btn_menu.mapToGlobal(QtCore.QPoint(0, self.btn_menu.height())))
    
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
            #AreaMenuButton {{
                background-color: transparent;
                color: {theme.get('text_main', '#E0E2E4')};
                border: none;
                border-radius: 2px;
                font-size: 12px;
                padding: 0px;
            }}
            #AreaMenuButton:hover {{
                background-color: {theme.get('bg_input', '#252930')};
                color: {theme.get('accent', '#5298D4')};
            }}
        """)


class RZAreaWidget(RZPanelWidget):
    """
    Container widget that hosts an RZEditorPanel with a header for type switching.
    Supports splitting into multiple areas and closing.
    
    Usage:
        area = RZAreaWidget()
        area.set_panel_type("OUTLINER")
        
        # Get the current panel instance
        panel = area.get_current_panel()
        
        # Split the area
        area.split_area(QtCore.Qt.Vertical)
    """
    
    # Signal emitted when the panel type changes
    panel_changed = QtCore.Signal(str, object)  # (panel_id, panel_instance)
    
    def __init__(self, initial_panel_id: str = None, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("RZAreaWidget")
        
        # Minimum size to prevent layout collapse
        self.setMinimumSize(QtCore.QSize(100, 100))
        
        # Ensure area expands to fill available space in splitter
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Expanding
        )
        
        self._current_panel: RZEditorPanel = None
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        self.header = RZAreaHeader(self)
        self.header.panel_type_changed.connect(self.change_panel)
        self.header.split_vertical_requested.connect(lambda: self.split_area(QtCore.Qt.Vertical))
        self.header.split_horizontal_requested.connect(lambda: self.split_area(QtCore.Qt.Horizontal))
        self.header.close_requested.connect(self.close_area)
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
    
    def split_area(self, orientation: QtCore.Qt.Orientation):
        """
        Split this area into two areas with the given orientation.
        
        Args:
            orientation: Qt.Vertical for side-by-side, Qt.Horizontal for top-bottom
        """
        parent = self.parent()
        
        # Must be inside a QSplitter
        if not isinstance(parent, QtWidgets.QSplitter):
            print(f"[RZAreaWidget] Cannot split: parent is not a QSplitter ({type(parent)})")
            return
        
        parent_splitter = parent
        current_panel_id = self.get_current_panel_id() or "OUTLINER"
        
        # Get current index and sizes
        my_index = parent_splitter.indexOf(self)
        old_sizes = parent_splitter.sizes()
        my_size = old_sizes[my_index] if my_index < len(old_sizes) else 200
        
        # Create new splitter with requested orientation
        new_splitter = QtWidgets.QSplitter(orientation)
        new_splitter.setChildrenCollapsible(False)
        
        # Create two new areas with the same panel type
        area1 = RZAreaWidget(initial_panel_id=current_panel_id)
        area2 = RZAreaWidget(initial_panel_id=current_panel_id)
        
        new_splitter.addWidget(area1)
        new_splitter.addWidget(area2)
        
        # Split the size evenly between the two new areas
        half_size = my_size // 2
        new_splitter.setSizes([half_size, half_size])
        
        # Replace self in parent splitter with new splitter
        parent_splitter.insertWidget(my_index, new_splitter)
        
        # Deactivate current panel before deletion
        if self._current_panel:
            self._current_panel.on_deactivate()
        
        # Remove and delete self
        self.setParent(None)
        self.deleteLater()
        
        # Restore parent splitter sizes (adjust for replacement)
        new_sizes = old_sizes.copy()
        new_sizes[my_index] = my_size
        parent_splitter.setSizes(new_sizes)
    
    def close_area(self):
        """
        Close this area, removing it from the parent splitter.
        """
        parent = self.parent()
        
        # Must be inside a QSplitter
        if not isinstance(parent, QtWidgets.QSplitter):
            print(f"[RZAreaWidget] Cannot close: parent is not a QSplitter ({type(parent)})")
            return
        
        parent_splitter = parent
        
        # Don't close if this is the last area in the root splitter
        # Check if parent splitter is inside another splitter
        grandparent = parent_splitter.parent()
        is_nested = isinstance(grandparent, QtWidgets.QSplitter)
        
        # Count siblings
        sibling_count = parent_splitter.count()
        
        if sibling_count <= 1 and not is_nested:
            # This is the last area in root splitter, don't allow closing
            print("[RZAreaWidget] Cannot close: this is the last area")
            return
        
        # Deactivate current panel
        if self._current_panel:
            self._current_panel.on_deactivate()
        
        # Get our index and sizes before removal
        my_index = parent_splitter.indexOf(self)
        old_sizes = parent_splitter.sizes()
        
        # Remove self
        self.setParent(None)
        self.deleteLater()
        
        # If parent splitter now has only one child and is nested, flatten it
        if parent_splitter.count() == 1 and is_nested:
            remaining_widget = parent_splitter.widget(0)
            if remaining_widget:
                grandparent_splitter = grandparent
                splitter_index = grandparent_splitter.indexOf(parent_splitter)
                
                # Move remaining widget to grandparent
                remaining_widget.setParent(None)
                grandparent_splitter.insertWidget(splitter_index, remaining_widget)
                
                # Remove empty splitter
                parent_splitter.setParent(None)
                parent_splitter.deleteLater()
        else:
            # Redistribute sizes among remaining widgets
            if old_sizes and my_index < len(old_sizes):
                freed_size = old_sizes[my_index]
                new_sizes = [s for i, s in enumerate(old_sizes) if i != my_index]
                if new_sizes:
                    # Add freed size to adjacent widget
                    distribute_to = min(my_index, len(new_sizes) - 1)
                    new_sizes[distribute_to] += freed_size
                    parent_splitter.setSizes(new_sizes)
    
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
