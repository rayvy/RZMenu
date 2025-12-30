# RZMenu/qt_editor/widgets/outliner.py
from PySide6 import QtWidgets, QtCore, QtGui

class RZDraggableTree(QtWidgets.QTreeWidget):
    """
    Дерево элементов с поддержкой Drag & Drop (re-parenting).
    """
    # Signal: (target_id, insert_after_id_OR_new_parent_id)
    # В данном контексте передаем (moved_id, new_parent_id)
    internal_reorder_signal = QtCore.Signal(int, object) 

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

    def dropEvent(self, event):
        # 1. Получаем список элементов, которые перетаскивали (до того, как Qt их переместит)
        source_items = self.selectedItems()
        if not source_items:
            return

        # 2. Вызываем стандартную логику Qt, чтобы визуально переместить айтемы
        super().dropEvent(event)

        # 3. Определяем, куда они упали (кто теперь их родитель)
        # Т.к. мы уже вызвали super(), иерархия обновилась. Проверяем первого перемещенного.
        # В реальном приложении нужно проверять все, но обычно перемещают пачку в одно место.
        first_item = source_items[0]
        moved_id = first_item.data(0, QtCore.Qt.UserRole)
        
        parent_item = first_item.parent()
        new_parent_id = None
        
        if parent_item:
            new_parent_id = parent_item.data(0, QtCore.Qt.UserRole)
        else:
            # Если parent_item is None, значит упал в корень (Root)
            new_parent_id = None 

        # 4. Эмитим сигнал обновления данных
        self.internal_reorder_signal.emit(moved_id, new_parent_id)


class RZMOutlinerPanel(QtWidgets.QWidget):
    # (selected_ids, active_id)
    selection_changed = QtCore.Signal(list, int)
    # (target_id, insert_after_id) -> интерпретируем как (id, new_parent)
    items_reordered = QtCore.Signal(int, object)

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = RZDraggableTree()
        # Пробрасываем сигнал из дерева наружу
        self.tree.internal_reorder_signal.connect(self.items_reordered)
        self.tree.itemSelectionChanged.connect(self._on_qt_selection_changed)

        # Styles
        self.tree.setStyleSheet("""
            QTreeWidget { background-color: #2b2b2b; border: none; font-size: 12px; }
            QTreeWidget::item { padding: 4px; color: #e0e0e0; }
            QTreeWidget::item:selected { background-color: #405560; color: white; }
            QTreeWidget::item:hover { background-color: #333; }
        """)

        layout.addWidget(self.tree)
        self._block_signals = False

    def _on_qt_selection_changed(self):
        if self._block_signals:
            return

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
        elements_list: list of dicts {'id', 'name', 'parent_id', 'class_type', 'is_hidden', ...}
        """
        self._block_signals = True
        
        # Save state (expanded items)
        expanded_ids = set()
        it = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.isExpanded():
                expanded_ids.add(item.data(0, QtCore.Qt.UserRole))
            it += 1

        self.tree.clear()
        
        # Maps
        id_map = {d['id']: d for d in elements_list}
        item_map = {}

        # Create Items
        for data in elements_list:
            item = QtWidgets.QTreeWidgetItem()
            item.setText(0, data.get('name', 'Unnamed'))
            item.setData(0, QtCore.Qt.UserRole, data['id'])
            
            # Icons based on type
            ctype = data.get('class_type', 'CONTAINER')
            icon = QtWidgets.QStyle.SP_FileIcon
            if "CONTAINER" in ctype: icon = QtWidgets.QStyle.SP_DirIcon
            elif "BUTTON" in ctype: icon = QtWidgets.QStyle.SP_DialogOkButton
            elif "TEXT" in ctype: icon = QtWidgets.QStyle.SP_FileDialogDetailedView
            item.setIcon(0, self.style().standardIcon(icon))

            # Column 1: Visible
            vis_char = "👁" if not data.get('is_hidden', False) else "❌"
            item.setText(1, vis_char)
            item.setTextAlignment(1, QtCore.Qt.AlignCenter)

            # Column 2: Selectable (Visual only for now)
            item.setText(2, "➤") 
            item.setTextAlignment(2, QtCore.Qt.AlignCenter)
            
            item_map[data['id']] = item

        # Build Hierarchy
        for data in elements_list:
            uid = data['id']
            pid = data.get('parent_id')
            item = item_map[uid]

            if pid is not None and pid in item_map:
                parent_item = item_map[pid]
                parent_item.addChild(item)
            else:
                self.tree.addTopLevelItem(item)

        # Restore state
        for uid, item in item_map.items():
            if uid in expanded_ids or item.parent() is None:
                item.setExpanded(True)

        self._block_signals = False

    def set_selection_silent(self, ids_set, active_id):
        self._block_signals = True
        self.tree.clearSelection()
        
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