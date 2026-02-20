# RZMenu/qt_editor/widgets/outliner.py
"""
Outliner Panel - Hierarchical tree view of menu elements.
Autonomous panel that subscribes to core.SIGNALS for data updates.
"""
from PySide6 import QtWidgets, QtCore, QtGui
from .. import core
from ..core.signals import SIGNALS
from ..context import RZContextManager
from ..utils.icons import IconManager
from .lib.theme import get_current_theme
from .lib.trees import RZDraggableTreeWidget
from .panel_base import RZEditorPanel


class RZDraggableTree(RZDraggableTreeWidget):
    """
    Drag & Drop enabled tree with specific column interactions for outliner.
    """
    # Signals for column clicks: (element_id)
    toggle_hide_signal = QtCore.Signal(int)
    toggle_selectable_signal = QtCore.Signal(int)

    def __init__(self):
        super().__init__()

        self.setHeaderLabels(["Name", "👁", "➤"]) 
        header = self.header()
        header.setStretchLastSection(False) 
        header.setMinimumSectionSize(20) # Allow smaller columns if needed
        
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        
        header.resizeSection(1, 26) # Slightly larger than 24 to be safe with icons
        header.resizeSection(2, 26)
        
        # Ensure header sections are centered for icons
        header.setDefaultAlignment(QtCore.Qt.AlignCenter)

    def _on_item_clicked(self, item, column):
        """Override base class to handle specific column clicks."""
        elem_id = item.data(0, QtCore.Qt.UserRole)
        if elem_id is None:
            return

        if column == 1:
            # Visibility Column
            self.toggle_hide_signal.emit(elem_id)
        elif column == 2:
            # Selectable/Locked Column
            self.toggle_selectable_signal.emit(elem_id)
        else:
            # For column 0, call parent handler
            super()._on_item_clicked(item, column)

    # REMOVED broken dropEvent override. 
    # Base class RZDraggableTreeWidget provides correct dropEvent implementation.


class RZMOutlinerPanel(RZEditorPanel):
    """
    Hierarchical tree view of all elements in the menu structure.
    
    AUTONOMOUS: Subscribes to SIGNALS.structure_changed, SIGNALS.selection_changed,
    SIGNALS.data_changed to update itself without window.py intervention.
    """
    
    # Panel Registry Metadata
    PANEL_ID = "OUTLINER"
    PANEL_NAME = "Outliner"
    PANEL_ICON = "list"
    
    # Signals for external communication (reordering, selection from user)
    selection_changed = QtCore.Signal(list, int)
    items_reordered = QtCore.Signal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("RZMOutlinerPanel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = RZDraggableTree()
        
        # Internal tree signals -> panel handlers
        self.tree.items_reordered.connect(self._on_items_reordered)
        self.tree.itemSelectionChanged.connect(self._on_qt_selection_changed)
        self.tree.toggle_hide_signal.connect(self._on_toggle_hide)
        self.tree.toggle_selectable_signal.connect(self._on_toggle_selectable)

        layout.addWidget(self.tree)
        self._block_signals = False
        self.setMouseTracking(True)

    def _connect_signals(self):
        """Connect to core signals for autonomous updates."""
        SIGNALS.structure_changed.connect(self.refresh_data)
        SIGNALS.selection_changed.connect(self.sync_selection)
        SIGNALS.data_changed.connect(self.refresh_data)
    
    def _disconnect_signals(self):
        """Disconnect from core signals to prevent calls to deleted objects."""
        try:
            SIGNALS.structure_changed.disconnect(self.refresh_data)
        except (RuntimeError, TypeError):
            pass
        try:
            SIGNALS.selection_changed.disconnect(self.sync_selection)
        except (RuntimeError, TypeError):
            pass
        try:
            SIGNALS.data_changed.disconnect(self.refresh_data)
        except (RuntimeError, TypeError):
            pass
    
    def refresh_data(self):
        """Fetch and display current element list from core."""
        if not self._is_panel_active:
            return
        data = core.get_all_elements_list()
        self.update_ui(data)
        # Also sync selection after data refresh
        self.sync_selection()
    
    def sync_selection(self):
        """Sync tree selection with context manager."""
        if not self._is_panel_active:
            return
        ctx = RZContextManager.get_instance().get_snapshot()
        self.set_selection_silent(ctx.selected_ids, ctx.active_id)

    def _on_items_reordered(self, target_id, new_parent_id):
        """Handle drag-drop reparenting and broadcast to all panels."""
        # Logic: If new_parent_id is None, it means the item was dropped to root (-1)
        pid = new_parent_id if new_parent_id is not None else -1
        core.reparent_element(target_id, pid)
        # Force signal explicitly because core.reparent_element emits it, 
        # but just to be sure we are aligned with the flow.
        # Actually core.reparent_element already emits structure_changed.
    
    def _on_toggle_hide(self, uid):
        """Handle visibility toggle via action manager."""
        am = self.get_action_manager()
        if am:
            am.run("rzm.toggle_hide", override_ids=[uid])
    
    def _on_toggle_selectable(self, uid):
        """Handle selectable toggle via action manager."""
        am = self.get_action_manager()
        if am:
            am.run("rzm.toggle_selectable", override_ids=[uid])

    def update_theme_styles(self):
        """Re-apply tree styling."""
        if hasattr(self, 'tree'):
            self.tree.apply_theme()
            # Хамское обновление, чтобы перерисовались хедеры
            self.tree.style().unpolish(self.tree)
            self.tree.style().polish(self.tree)

    def enterEvent(self, event):
        RZContextManager.get_instance().update_input(
            QtGui.QCursor.pos(), (0.0, 0.0), area="OUTLINER"
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        RZContextManager.get_instance().update_input(
            QtGui.QCursor.pos(), (0.0, 0.0), area="NONE"
        )
        super().leaveEvent(event)

    def _on_qt_selection_changed(self):
        """Handle user selection in tree -> update context manager."""
        if self._block_signals: return

        selected_items = self.tree.selectedItems()
        ids = [item.data(0, QtCore.Qt.UserRole) for item in selected_items]
        
        current = self.tree.currentItem()
        active_id = -1
        if current and current in selected_items:
            active_id = current.data(0, QtCore.Qt.UserRole)
        elif ids:
            active_id = ids[0]

        # Update context manager directly (which will emit selection_changed)
        RZContextManager.get_instance().set_selection(set(ids), active_id)

    def update_ui(self, elements_list):
        self._block_signals = True

        expanded_ids = self.tree.get_expanded_item_ids()
        self.tree.clear()
        
        if not elements_list:
            self._block_signals = False
            return

        item_map = {}
        theme = get_current_theme()
        disabled_color = QtGui.QColor(theme.get('text_disabled', '#999999'))
        
        for data in elements_list:
            item = QtWidgets.QTreeWidgetItem()
            uid = data['id']
            item.setText(0, data.get('name', 'Unnamed'))
            item.setData(0, QtCore.Qt.UserRole, uid)
            
            ctype = data.get('class_type', 'CONTAINER')
            
            # MODERNIZATION: Custom Icon System with Fallback
            icon_map = {
                "CONTAINER": ("folder", QtWidgets.QStyle.StandardPixmap.SP_DirIcon),
                "BUTTON": ("button", QtWidgets.QStyle.StandardPixmap.SP_DialogOkButton),
                "TEXT": ("text", QtWidgets.QStyle.StandardPixmap.SP_FileIcon),
                "SLIDER": ("slider", QtWidgets.QStyle.StandardPixmap.SP_ToolBarHorizontalExtensionButton),
                "GRID_CONTAINER": ("grid", QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView),
            }
            
            name, sp = icon_map.get(ctype, ("file", QtWidgets.QStyle.StandardPixmap.SP_FileIcon))
            icon = IconManager.get_instance().get_icon(name, fallback_sp=sp)
            item.setIcon(0, icon)

            is_hidden = data.get('is_hidden', False)
            item.setText(1, "❌" if is_hidden else "👁")
            item.setTextAlignment(1, QtCore.Qt.AlignCenter)
            if is_hidden:
                item.setForeground(0, disabled_color)

            is_sel = data.get('is_selectable', True)
            item.setText(2, "➤" if is_sel else "🔒")
            item.setTextAlignment(2, QtCore.Qt.AlignCenter)
            
            item_map[uid] = item

        for data in elements_list:
            uid = data['id']
            pid = data.get('parent_id', -1)
            if uid in item_map:
                item = item_map[uid]
                if pid in item_map and pid != uid:
                    item_map[pid].addChild(item)
                else:
                    self.tree.addTopLevelItem(item)

        self.tree.set_expanded_items(expanded_ids)

        self._block_signals = False

    def set_selection_silent(self, ids_set, active_id):
        self._block_signals = True
        self.tree.clearSelection()
        
        if not ids_set:
            self._block_signals = False
            return

        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        item_to_focus = None
        while it.value():
            item = it.value()
            uid = item.data(0, QtCore.Qt.UserRole)
            if uid in ids_set:
                item.setSelected(True)
                if uid == active_id:
                    item_to_focus = item
            it += 1
        
        if item_to_focus:
            self.tree.setCurrentItem(item_to_focus)
            self.tree.scrollToItem(item_to_focus)

        self._block_signals = False
