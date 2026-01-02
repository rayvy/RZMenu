# RZMenu/qt_editor/widgets/outliner.py
from PySide6 import QtWidgets, QtCore, QtGui
from ..context import RZContextManager
from .lib.theme import get_current_theme
from .lib.trees import RZDraggableTreeWidget
from .lib.widgets import RZPanelWidget

class RZDraggableTree(RZDraggableTreeWidget):
    """
    Drag & Drop enabled tree with specific column interactions for outliner.
    """
    # Signals for column clicks: (element_id)
    toggle_hide_signal = QtCore.Signal(int)
    toggle_selectable_signal = QtCore.Signal(int)

    def __init__(self):
        super().__init__()

        self.setHeaderLabels(["Name", "Vis", "Sel"])
        self.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        self.setColumnWidth(1, 30)
        self.setColumnWidth(2, 30)

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
        source_items = self.selectedItems()
        if not source_items: return

        # Стандартная обработка перемещения Qt
        super().dropEvent(event)

        # Вычисляем, куда упало
        first_item = source_items[0]
        moved_id = first_item.data(0, QtCore.Qt.UserRole)
        
        parent_item = first_item.parent()
        new_parent_id = None
        
        if parent_item:
            new_parent_id = parent_item.data(0, QtCore.Qt.UserRole)
        
        self.internal_reorder_signal.emit(moved_id, new_parent_id)


class RZMOutlinerPanel(RZPanelWidget):
    selection_changed = QtCore.Signal(list, int)
    items_reordered = QtCore.Signal(int, object)
    
    req_toggle_hide = QtCore.Signal(int)
    req_toggle_selectable = QtCore.Signal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName("RZMOutlinerPanel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = RZDraggableTree()
        
        self.tree.items_reordered.connect(self.items_reordered)
        self.tree.itemSelectionChanged.connect(self._on_qt_selection_changed)
        self.tree.toggle_hide_signal.connect(self.req_toggle_hide)
        self.tree.toggle_selectable_signal.connect(self.req_toggle_selectable)

        layout.addWidget(self.tree)
        self._block_signals = False
        self.setMouseTracking(True)

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
        if self._block_signals: return

        selected_items = self.tree.selectedItems()
        ids = [item.data(0, QtCore.Qt.UserRole) for item in selected_items]
        
        current = self.tree.currentItem()
        active_id = -1
        if current and current in selected_items:
            active_id = current.data(0, QtCore.Qt.UserRole)
        elif ids:
            active_id = ids[0]

        self.selection_changed.emit(ids, active_id)

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
            icon = QtWidgets.QStyle.SP_FileIcon
            if "CONTAINER" in ctype: icon = QtWidgets.QStyle.SP_DirIcon
            elif "BUTTON" in ctype: icon = QtWidgets.QStyle.SP_DialogOkButton
            elif "TEXT" in ctype: icon = QtWidgets.QStyle.SP_FileDialogDetailedView
            item.setIcon(0, self.style().standardIcon(icon))

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