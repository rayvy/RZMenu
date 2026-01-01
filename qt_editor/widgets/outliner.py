# RZMenu/qt_editor/widgets/outliner.py
from PySide6 import QtWidgets, QtCore, QtGui
from ..context import RZContextManager

class RZDraggableTree(QtWidgets.QTreeWidget):
    """
    Drag & Drop enabled tree with specific column interactions.
    """
    internal_reorder_signal = QtCore.Signal(int, object) 
    
    # Signals for column clicks: (element_id)
    toggle_hide_signal = QtCore.Signal(int)
    toggle_selectable_signal = QtCore.Signal(int)

    def __init__(self):
        super().__init__()
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)
        
        self.setHeaderLabels(["Name", "Vis", "Sel"])
        self.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        self.setColumnWidth(1, 30)
        self.setColumnWidth(2, 30)
        
        self.itemClicked.connect(self._on_item_clicked)

    def _on_item_clicked(self, item, column):
        elem_id = item.data(0, QtCore.Qt.UserRole)
        if elem_id is None: return

        if column == 1:
            # Visibility Column
            self.toggle_hide_signal.emit(elem_id)
            # Оптимистичное обновление UI (пока ждем ответа от Blender)
            curr = item.text(1)
            item.setText(1, "❌" if curr == "👁" else "👁")
            
        elif column == 2:
            # Selectable/Locked Column
            self.toggle_selectable_signal.emit(elem_id)
            curr = item.text(2)
            item.setText(2, "🔒" if curr == "➤" else "➤")

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


class RZMOutlinerPanel(QtWidgets.QWidget):
    selection_changed = QtCore.Signal(list, int)
    items_reordered = QtCore.Signal(int, object)
    
    req_toggle_hide = QtCore.Signal(int)
    req_toggle_selectable = QtCore.Signal(int)

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = RZDraggableTree()
        
        # Wiring internal tree signals
        self.tree.internal_reorder_signal.connect(self.items_reordered)
        self.tree.itemSelectionChanged.connect(self._on_qt_selection_changed)
        self.tree.toggle_hide_signal.connect(self.req_toggle_hide)
        self.tree.toggle_selectable_signal.connect(self.req_toggle_selectable)

        # Styles
        self.tree.setStyleSheet("""
            QTreeWidget { background-color: #2b2b2b; border: none; font-size: 12px; }
            QTreeWidget::item { padding: 4px; color: #e0e0e0; }
            QTreeWidget::item:selected { background-color: #405560; color: white; }
            QTreeWidget::item:hover { background-color: #333; }
        """)

        layout.addWidget(self.tree)
        self._block_signals = False
        
        # Enable mouse tracking for hover detection if needed in future
        self.setMouseTracking(True)

    def enterEvent(self, event):
        RZContextManager.get_instance().update_input(
            QtGui.QCursor.pos(),
            (0.0, 0.0),
            set(), # Пустые модификаторы или можно читать через QApplication.keyboardModifiers()
            area="OUTLINER"
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        RZContextManager.get_instance().update_input(
            QtGui.QCursor.pos(),
            (0.0, 0.0),
            set(),
            area="NONE"
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
        """
        Rebuilds the tree.
        """
        self._block_signals = True
        
        # 1. Save state (expanded items)
        expanded_ids = set()
        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.isExpanded():
                expanded_ids.add(item.data(0, QtCore.Qt.UserRole))
            it += 1

        self.tree.clear()
        
        if not elements_list:
            self._block_signals = False
            return

        # 2. Create all items map
        item_map = {}
        
        for data in elements_list:
            item = QtWidgets.QTreeWidgetItem()
            uid = data['id']
            item.setText(0, data.get('name', 'Unnamed'))
            item.setData(0, QtCore.Qt.UserRole, uid)
            
            # Icons based on class
            ctype = data.get('class_type', 'CONTAINER')
            icon = QtWidgets.QStyle.SP_FileIcon
            if "CONTAINER" in ctype: icon = QtWidgets.QStyle.SP_DirIcon
            elif "BUTTON" in ctype: icon = QtWidgets.QStyle.SP_DialogOkButton
            elif "TEXT" in ctype: icon = QtWidgets.QStyle.SP_FileDialogDetailedView
            item.setIcon(0, self.style().standardIcon(icon))

            # Column 1: Visible
            # Logic: is_hidden=True -> X, else Eye
            is_hidden = data.get('is_hidden', False)
            vis_char = "❌" if is_hidden else "👁"
            item.setText(1, vis_char)
            item.setTextAlignment(1, QtCore.Qt.AlignCenter)
            # Подкрасим скрытые
            if is_hidden:
                item.setForeground(0, QtGui.QColor("#888"))

            # Column 2: Selectable
            is_sel = data.get('is_selectable', True)
            sel_char = "➤" if is_sel else "🔒"
            item.setText(2, sel_char)
            item.setTextAlignment(2, QtCore.Qt.AlignCenter)
            
            item_map[uid] = item

        # 3. Build Hierarchy
        for data in elements_list:
            uid = data['id']
            pid = data.get('parent_id', -1)
            item = item_map[uid]

            if pid in item_map and pid != uid:
                parent_item = item_map[pid]
                parent_item.addChild(item)
            else:
                self.tree.addTopLevelItem(item)

        # 4. Restore state
        for uid, item in item_map.items():
            if uid in expanded_ids:
                item.setExpanded(True)
            # Expand root by default if needed
            if item.parent() is None:
                item.setExpanded(True)

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