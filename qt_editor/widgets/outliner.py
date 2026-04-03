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

        self.setHeaderLabels(["Name", "", ""]) 
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

    def dropEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat("application/x-rzmenu-image-id"):
            data = mime.data("application/x-rzmenu-image-id")
            try:
                image_id = int(data.data().decode('utf-8'))
                target_item = self.itemAt(event.pos())
                if target_item:
                    target_uid = target_item.data(0, QtCore.Qt.UserRole)
                    core.update_property_multi([target_uid], "image_id", image_id)
                event.accept()
                return
            except ValueError:
                pass
                
        super().dropEvent(event)


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

        self.tree = RZDraggableTree()
        
        # Internal tree signals -> panel handlers
        self.tree.items_reordered.connect(self._on_items_reordered)
        self.tree.itemSelectionChanged.connect(self._on_qt_selection_changed)
        self.tree.itemChanged.connect(self._on_tree_item_changed)
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
        SIGNALS.isolation_changed.connect(self.refresh_data)
    
    def _disconnect_signals(self):
        """Disconnect from core signals to prevent calls to deleted objects."""
        try:
            from ..core.signals import SIGNALS
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
        
        # SAVE SCROLL POSITION
        scroll_bar = self.tree.verticalScrollBar()
        old_scroll = scroll_bar.value()

        elements_list = core.get_all_elements_list()
        if not elements_list:
            # If no elements, clear tree and reset block_signals
            self._block_signals = True # Block signals during clear
            self.tree.clear()
            self._block_signals = False
            return
        
        self.update_ui(elements_list)
        # Also sync selection after data refresh
        self.sync_selection()

        # RESTORE SCROLL POSITION
        # We use a singleShot to apply it after visual layout is ready.
        QtCore.QTimer.singleShot(0, lambda: scroll_bar.setValue(old_scroll))
    

    def sync_selection(self):
        """Sync tree selection with context manager."""
        if not self._is_panel_active:
            return
        ctx = RZContextManager.get_instance().get_snapshot()
        self.set_selection_silent(ctx.selected_ids, ctx.active_id)

    def _on_items_reordered(self, target_ids, new_parent_id, sibling_ids):
        """Handle drag-drop reparenting for multiple items and normalize priorities."""
        # 1. First move items to the new parent
        for tid in target_ids:
            core.reparent_element(tid, new_parent_id, silent=True)
        
        # 2. Normalize priorities of ALL siblings to match the visual order in the tree
        # We use a step of 10 to leave gaps for manual adjustments
        for i, sid in enumerate(sibling_ids):
            core.update_property_multi([sid], "qt_priority", i * 10)
        
        # Trigger global updates
        SIGNALS.structure_changed.emit()
        SIGNALS.transform_changed.emit()
    
    def _on_tree_item_changed(self, item, column):
        if self._block_signals: return
        if column == 0:
            uid = item.data(0, QtCore.Qt.UserRole)
            new_name = item.text(0)
            core.update_property_multi([uid], "element_name", new_name)
    
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

        # SORT BY QT_PRIORITY
        # Blender data might not be sorted, so we do it here for visual order
        elements_list = sorted(elements_list, key=lambda x: x.get('qt_priority', 0))

        # --- TAB ISOLATOR - VIEWPORT CONTROL ONLY (Logic removed from Outliner) ---
        # We no longer filter 'elements_list' here, so the tree shows everything.
        # ---------------------------------------------
        # -------------------------------

        item_map = {}
        theme = get_current_theme()
        disabled_color = QtGui.QColor(theme.get('text_disabled', '#999999'))
        
        for data in elements_list:
            item = QtWidgets.QTreeWidgetItem()
            uid = data['id']
            item.setText(0, data.get('name', 'Unnamed'))
            item.setData(0, QtCore.Qt.UserRole, uid)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
            
            ctype = data.get('class_type', 'CONTAINER')
            
            # MODERNIZATION: Custom Icon System with Phosphor SVGs
            icon_map = {
                "CONTAINER": "folder",
                "BUTTON": "cursor-click",
                "TEXT": "text-t",
                "SLIDER": "sliders",
                "GRID_CONTAINER": "grid-four",
            }
            
            # Page Indication Highlight
            if data.get('is_tab_container'):
                col = data.get('page_color', [0.5, 0.5, 0.5, 1.0])
                qcol = QtGui.QColor.fromRgbF(col[0], col[1], col[2], 1.0)
                item.setForeground(0, qcol)
                # Bold for Page roots
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)

            name = icon_map.get(ctype, "file")
            icon = IconManager.get_instance().get_icon(name, color="text_light")
            item.setIcon(0, icon)

            is_hidden = data.get('is_hidden', False)
            vis_icon = IconManager.get_instance().get_icon("eye" if not is_hidden else "eye-slash", 
                                                         color="accent" if not is_hidden else "text_disabled")
            item.setIcon(1, vis_icon)
            item.setText(1, "") # Icon only
            item.setTextAlignment(1, QtCore.Qt.AlignCenter)
            if is_hidden:
                item.setForeground(0, disabled_color)

            is_sel = data.get('is_selectable', True)
            sel_icon = IconManager.get_instance().get_icon("cursor" if is_sel else "lock-simple",
                                                         color="accent" if is_sel else "text_disabled") 
            item.setIcon(2, sel_icon)
            item.setText(2, "") # Icon only
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
